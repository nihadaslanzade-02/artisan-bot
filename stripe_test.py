import stripe

stripe.api_key = "sk_test_51RI768FMAITTYODT9yYoOpcyTgZ1NSc6YNrIuyAg0eHNOF8Ty3GHVjMtn009Zr508Ngj6kscVYLVNrd4d6tV2reX00lcjg0h1r"  # Test secret açarını yaz

# Əvvəlcə Product və Price yaradırıq
product = stripe.Product.create(name="Usta Xidmət Ödənişi")

price = stripe.Price.create(
    product=product.id,
    unit_amount=5000,  # 50.00 EUR
    currency="eur",
)

print("✅ Price yaradıldı:")
print(price.id)
