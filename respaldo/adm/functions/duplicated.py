class NoDuplicate():
    def no_duplicate(query):
        acc = []
        for a in query:
            counter = 0
            for count in acc:
                if count.email == a.email:
                    counter += 1
            if counter == 0:
                acc.append(a)
        return acc