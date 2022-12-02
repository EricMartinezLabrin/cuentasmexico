import csv
class Country():

    def get_country_lada():
        file = csv.reader(open('adm/db/paises.csv',encoding='utf-8'))
        data={}
        for f in file:
            data[f[0]] = f[5]
        return data