import os
import sys

# Add Odoo paths if needed, or we can just use odoo shell like before
# Let's run a script through odoo shell.
print("""
logs = env['dealflow.approval.log'].search([], order='id desc', limit=10)
for log in logs:
    print(f"Log ID: {log.id}, Order: {log.order_id.id}, Action: {log.action}, Reason: {log.reason}")
""")
