from delta import html, Delta

d1 = Delta()
d1.insert("Hallo du!")
d2 = Delta().delete(2)
d1 = d1.compose(d2)
d1.insert("More stuff")
d3 = Delta([{"insert" : "Jdöfl"}])
d1 = d3.compose(d1)
print(html.render(d1))

for line, attrs, index in d1.iter_lines():
    print(line, attrs, index)