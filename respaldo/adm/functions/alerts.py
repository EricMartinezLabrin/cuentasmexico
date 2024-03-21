class Alerts():
    def does_not_exist(classname,url,male=True):
        if male == False:
            a = 'a'
        else:
            a = ' '

        return(f'Aún no existe ningun{a}  {classname}, puedes crear una haciendo click <a href="{url}" class="alert-link">aquí</a>')