import csv
class Country():

    def get_country_lada():
        file = csv.reader(open('adm/db/paises.csv'))
        data={}
        for f in file:
            data[f[0]] = f[5]
        return data