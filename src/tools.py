import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List


def send_email(
	to: str,
	subject: str,
	body: str,
):
	"""
	Send real email using Gmail SMTP. Requires EMAIL_ADDRESS and
	EMAIL_APP_PASSWORD to be set in the environment.
	"""

	EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
	EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

	if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
		raise RuntimeError("EMAIL_ADDRESS and EMAIL_APP_PASSWORD must be set in environment")

	try:
		message = MIMEMultipart()
		message["From"] = EMAIL_ADDRESS
		message["To"] = to
		message["Subject"] = subject
		message.attach(MIMEText(body, "plain"))

		with smtplib.SMTP("smtp.gmail.com", 587) as server:
			server.starttls()
			server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
			server.sendmail(EMAIL_ADDRESS, to, message.as_string())

		return f"Email successfully sent to {to}"

	except Exception as e:
		return f"Failed to send email: {str(e)}"


tools: List = [send_email]
