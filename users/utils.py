import random
import string as string_module

def generate_otp():
    return ''.join(random.choices(string_module.digits, k=6))