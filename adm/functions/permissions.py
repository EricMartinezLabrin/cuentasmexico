from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import redirect


class UserAccessMixin(PermissionRequiredMixin):
    """
    Check requeriments before access page, if not hace it redirect to login page
    """

    def dispatch(self, request, *args, **kwargs):
        # Check if initial information are declarated
        # InitialData.check_data(request)

        if (not self.request.user.is_authenticated):
            return redirect_to_login(self.request.get_full.path(),
                                     self.get_login_url(), self.get_redirect_field_name())

        if not self.has_permission():
            if request.user.is_staff:
                return redirect('adm:no-permission')
            else:
                return redirect('index')
        return super(UserAccessMixin, self).dispatch(request, *args, *kwargs)
