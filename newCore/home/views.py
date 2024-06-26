from django.shortcuts import render,redirect ,get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth import login,logout , authenticate
from django.contrib import messages
from django.contrib.auth.models import Group
from .forms import CustomUserCreationForm 
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from . import forms
from .models import Doctor, TimeSlot, CustomUser , Patient
from .forms import TimeSlotForm , DoctorProfileForm , PatientProfileForm, PrescriptionForm
import calendar
from datetime import datetime , timedelta
from django.http import Http404




#home page
@never_cache
def home(request):
    return render(request, 'home.html')


#login view
@never_cache
def login_user(request):
    
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('home'))  
                             
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            return redirect('home')
            

        else:
            messages.error(request, "Invalid information. Please try again")

    return render(request, 'login.html', {})



# sign up view
@never_cache
def signup(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('home'))   
                            
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)

                if user.role == 'doctor':
                    Doctor.objects.create(user=user)

                if user.role == 'patient':
                    Patient.objects.create(user=user)

                if user.role == 'doctor':
                    return redirect('add_profile')

                else :

                 return redirect('home')
                

            else:
                return redirect('signup')
    else:
        form = CustomUserCreationForm()
    return render(request, 'signup.html', {'form': form}) 



# logout view
def logout_user(request):
    logout(request)
    return redirect('home')




@login_required
def dashboard(request):
    user = request.user 

    if user.role == 'doctor':

        if user.doctor.is_approved:   
            return render(request,'dashboard.html' , {'user' : user})
        else:
            raise Http404("You don't have enough permissions !!")
        
    else :
    
         return render(request,'dashboard.html' , {'user' : user})



#########################################################################################################################

# patient related views

@login_required
def patient_dashboard(request):
    return render(request, 'dashboard.html')



def available_doctors(request):
    if request.user.role != 'patient':
        return redirect('home')

   
    department = request.GET.get('department')

    if department:
        doctors = Doctor.objects.filter(department=department)
    else:
        doctors = Doctor.objects.all()

    doctor_slots = {doctor: TimeSlot.objects.filter(doctor=doctor).order_by('date', 'start_time') for doctor in doctors}

    return render(request, 'available_doctors.html', {'doctor_slots': doctor_slots, 'selected_department': department})




@never_cache
@login_required
def update_profile_patient(request):

    try:
        patient = Patient.objects.get(user=request.user)

    except Patient.DoesNotExist:

        messages.error(request, 'You are not authorized to view this page.')
        return redirect('home')
    

    if request.method == 'POST':
        patient_profile_form = PatientProfileForm(request.POST, request.FILES, instance=patient)  

        if patient_profile_form.is_valid():
            patient_profile_form.save()
            # messages.success(request, 'Profile updated successfully.')
            return redirect('update_profile_patient') 


    else:

        patient_profile_form = PatientProfileForm(instance=patient)


    return render(request, 'update_profile_patient.html', {'patient_profile_form': patient_profile_form,})



@login_required
def book_appointment(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)
    slots = TimeSlot.objects.filter(doctor=doctor, booked=False).order_by('date', 'start_time')
    
    if request.method == 'POST':
        timeslot_id = request.POST.get('slot_id')
        timeslot = get_object_or_404(TimeSlot, id=timeslot_id)
        patient = get_object_or_404(Patient, user=request.user)  # Ensure we get the Patient instance

        timeslot.booked = True
        timeslot.patient = patient  # Assign the Patient instance
        timeslot.save()
        return redirect('confirm_booking', doctor_id=doctor.id, timeslot_id=timeslot.id)

    return render(request, 'book_appointment.html', {'doctor': doctor, 'slots': slots})



@login_required
def confirm_booking(request, doctor_id, timeslot_id):
    timeslot = get_object_or_404(TimeSlot, id=timeslot_id)
    return render(request, 'booking_confirmation.html', {'timeslot': timeslot})



def view_appointments_patient(request):

    patient = Patient.objects.get(user=request.user)
    appointments = TimeSlot.objects.filter(patient=patient, booked=True).order_by('date', 'start_time')
    return render(request, 'view_appointments_patient.html', {'appointments': appointments})


#################################################################################################################################



# doctor related views

@never_cache
@login_required
def add_availability(request):
    try:
        doctor = Doctor.objects.get(user=request.user,is_approved=True)
    except Doctor.DoesNotExist:
        return redirect('home')

    if request.method == 'POST':
        form = TimeSlotForm(request.POST)

        if form.is_valid():

            day = int(form.cleaned_data['day'])
            selected_time_slots = form.cleaned_data['time_slots']

            for slot in selected_time_slots:

                start_time_str, end_time_str = slot.split('-') 
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()
                date = get_next_weekday(datetime.now(), day) 


                # Check if the time slot already exists
                if TimeSlot.objects.filter(doctor=doctor, date=date, start_time=start_time, end_time=end_time).exists():
                    messages.warning(request, 'time slot already exists.')
                else:
                    TimeSlot.objects.create(doctor=doctor, date=date, start_time=start_time, end_time=end_time)
                    # messages.success(request, f'Time slot {start_time_str} - {end_time_str} on {date.strftime("%Y-%m-%d")} added successfully.')



            return redirect('add_availability')
    else:
        form = TimeSlotForm()

    time_slots = TimeSlot.objects.filter(doctor=doctor)
    slots_by_date = {} 

    for slot in time_slots:

        if slot.date not in slots_by_date:
            slots_by_date[slot.date] = []
        slots_by_date[slot.date].append(slot)


    return render(request, 'add_availability.html', {
        'form': form,
        'time_slots': time_slots,

    })




def get_next_weekday(start_date, weekday):
    days_ahead = weekday - start_date.weekday()
    if days_ahead <= 0: # Target day already happened this week
        days_ahead += 7
    return start_date + timedelta(days=days_ahead)



@login_required
def delete_time_slot(request, slot_id):
    time_slot = get_object_or_404(TimeSlot, id=slot_id)
    if time_slot.doctor.user != request.user:
        messages.error(request, 'You are not authorized to delete this time slot.')
        return redirect('add_availability')
    time_slot.delete()
    # messages.success(request, 'Time slot deleted successfully.')
    return redirect('add_availability')



@never_cache
@login_required
def add_profile(request):

    # if request.user.doctor.full_name :
    #     return redirect ('home')
    
    if request.user.doctor.full_name :
         return redirect ('home')
        

    try:
        doctor = Doctor.objects.get(user=request.user)

    except Doctor.DoesNotExist:

        # messages.error(request, 'You are not authorized to view this page.')
        return redirect('home')
    

    if request.method == 'POST':
        profile_form = DoctorProfileForm(request.POST, request.FILES, instance=doctor)  

        if profile_form.is_valid():
            profile_form.save()
            # messages.success(request, 'Profile updated successfully.')
            return redirect('home')


    else:

        profile_form = DoctorProfileForm(instance=doctor)


    return render(request, 'update_profile.html', {'profile_form': profile_form,})



@never_cache
@login_required
def update_profile(request):

    try:
        doctor = Doctor.objects.get(user=request.user)

    except Doctor.DoesNotExist:

        messages.error(request, 'You are not authorized to view this page.')
        return redirect('home')
    

    if request.method == 'POST':
        profile_form = DoctorProfileForm(request.POST, request.FILES, instance=doctor)  

        if profile_form.is_valid():
            profile_form.save()
            # messages.success(request, 'Profile updated successfully.')
            return redirect('update_profile') 


    else:

        profile_form = DoctorProfileForm(instance=doctor)


    return render(request, 'update_profile.html', {'profile_form': profile_form,})


@login_required
def doctor_view_appointments(request):
    doctor = get_object_or_404(Doctor, user=request.user)
    appointments = TimeSlot.objects.filter(doctor=doctor, booked=True).order_by('date', 'start_time')
    return render(request, 'doctor_view_appointments.html', {'appointments': appointments})

@login_required
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(TimeSlot, id=appointment_id)
    if request.method == 'POST':
        form = PrescriptionForm(request.POST, request.FILES, instance=appointment)
        if form.is_valid():
            form.save()
            return redirect('doctor_view_appointments')
    else:
        form = PrescriptionForm(instance=appointment)
    return render(request, 'appointment_detail.html', {'appointment': appointment, 'form': form})
