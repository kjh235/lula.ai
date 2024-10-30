from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# app = Flask(__name__)
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
# db = SQLAlchemy(app)

# from app import routes
"""https://stripe.com/docs/api/subscription_schedules/create"""

# import stripe
# stripe.api_key = "sk_test_4eC39HqLyjWDarjtT1zdp7dc"
#
# stripe.Product.create(name="Gold Special")
#
# stripe.Price.create(
#   unit_amount=11690,
#   currency="usd",
#   recurring={"interval": "month"},
#   product="prod_OlMCZ3L0fRXDyv",
# )
#
# stripe.SubscriptionSchedule.create(
#   start_date=1697229667,
#   end_behavior="release",
#   phases=[
#     {
#       "items": [
#         {
#           "price":
#           "price_1NjtJx2eZvKYlo2CrFESqfGi",
#           "quantity": 1,
#         },
#       ],
#       "iterations": 12,
#     },
#   ],
# )
#
#
