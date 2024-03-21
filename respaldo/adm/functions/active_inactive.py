from django.http import HttpResponse
from adm import models

class Active_Inactive():
    def active_inactive(status):
        """
        If status is Active, change to Inactive, if is Inactive, change to Active
        """
        if status == 'True':
            return False
        elif status == 'False':
            return True
        elif status == True:
            return False
        elif status == False:
            return True

    def a_or_i(status):
        if status == 'A':
            return True
        if status == 'I':
            return False
    
    def a_0_or_1(status):
        if status == '1':
            return True
        else:
            return False

    def activo_or_inactivo(status):
        if status == 'Activo':
            return True
        else:
            return False

