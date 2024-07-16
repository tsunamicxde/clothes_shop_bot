import math


def round_up_to_nearest_100(number):
    return math.ceil(number / 100) * 100


def calculate_discounted_price(price, discount_percentage):
    discounted_price = price * (1 - discount_percentage / 100)
    rounded_price = round_up_to_nearest_100(discounted_price)
    return rounded_price




