from django.shortcuts import render
from django.views.generic import TemplateView

class HomeView(TemplateView):
     template_name = "main/home.html"

class DesignSystemView(TemplateView):
     template_name = "main/ds.html"

# Create your views here.
