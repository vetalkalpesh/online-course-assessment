
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.contrib.auth.models import User
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
import logging

from .models import Course, Enrollment, Question, Choice, Submission

logger = logging.getLogger(__name__)


def registration_request(request):
    context = {}
    if request.method == 'GET':
        return render(
            request,
            'onlinecourse/user_registration_bootstrap.html',
            context
        )
    elif request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']

        user_exist = False
        try:
            User.objects.get(username=username)
            user_exist = True
        except User.DoesNotExist:
            logger.info("New user")

        if not user_exist:
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=password
            )
            login(request, user)
            return redirect("onlinecourse:index")
        else:
            context['message'] = "User already exists."
            return render(
                request,
                'onlinecourse/user_registration_bootstrap.html',
                context
            )


def login_request(request):
    context = {}
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "Invalid username or password."
            return render(
                request,
                'onlinecourse/user_login_bootstrap.html',
                context
            )
    else:
        return render(
            request,
            'onlinecourse/user_login_bootstrap.html',
            context
        )


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    if user.id is not None:
        return Enrollment.objects.filter(
            user=user,
            course=course
        ).exists()
    return False


class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]

        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)

        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    if user.is_authenticated:
        is_enrolled = check_if_enrolled(user, course)

        if not is_enrolled:
            Enrollment.objects.create(
                user=user,
                course=course,
                mode='honor'
            )
            course.total_enrollment += 1
            course.save()

    return HttpResponseRedirect(
        reverse(
            viewname='onlinecourse:course_details',
            args=(course.id,)
        )
    )


def submit(request, course_id):
    if request.method != 'POST':
        return redirect(
            'onlinecourse:course_details',
            pk=course_id
        )

    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    course = get_object_or_404(Course, pk=course_id)

    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course
    )

    submission = Submission.objects.create(
        enrollment=enrollment
    )

    for key, value in request.POST.items():
        if key.startswith('choice_'):
            try:
                choice = Choice.objects.get(
                    pk=int(value),
                    question__course=course
                )
                submission.choices.add(choice)
            except (ValueError, Choice.DoesNotExist):
                continue

    submission.completed = True
    submission.save()

    return redirect(
        'onlinecourse:show_exam_result',
        course_id=course.id,
        submission_id=submission.id
    )


def show_exam_result(request, course_id, submission_id):
    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    course = get_object_or_404(Course, pk=course_id)

    submission = get_object_or_404(
        Submission,
        pk=submission_id,
        enrollment__user=request.user,
        enrollment__course=course
    )

    questions = Question.objects.filter(
        course=course
    ).prefetch_related('choices')

    selected_choices = submission.choices.all()
    score = 0
    results = []

    for question in questions:
        correct_choices = question.choices.filter(
            is_correct=True
        )
        selected_for_question = selected_choices.filter(
            question=question
        )

        correct_ids = set(
            correct_choices.values_list('id', flat=True)
        )
        selected_ids = set(
            selected_for_question.values_list('id', flat=True)
        )

        is_correct = bool(correct_ids) and correct_ids == selected_ids

        if is_correct:
            score += question.grade

        results.append({
            'question': question,
            'selected_choices': selected_for_question,
            'correct_choices': correct_choices,
            'is_correct': is_correct,
        })

    context = {
        'course': course,
        'submission': submission,
        'results': results,
        'score': score,
        'total_score': sum(
            question.grade for question in questions
        ),
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )


