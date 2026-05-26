q = "Why is filtering important for LM35 readings?".lower()
keywords = ["tccr", "adcsra", "admux", "ddr", "portb", "porta"]
for k in keywords:
    if k in q:
        print(f"Matched keyword: {k}")
