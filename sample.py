import http.client

conn = http.client.HTTPSConnection("irctc1.p.rapidapi.com")

headers = {
    'x-rapidapi-key': "eb4159039dmsh45e1ea820759302p1fda60jsnc3c82cd3265c",
    'x-rapidapi-host': "irctc1.p.rapidapi.com"
}

conn.request("GET", "/api/v1/liveTrainStatus?trainNo=16605&startDay=0", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))


