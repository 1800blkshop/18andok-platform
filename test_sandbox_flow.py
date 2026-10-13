#!/usr/bin/env python3
import os

from safe_payment_wrapper import capture_pre_approved_customer_payment_safe

def main():
    intent_id = "intent-test-001"
    customer_id = "cus_test_123"
    payment_method_id = "pm_test_123"

    result = capture_pre_approved_customer_payment_safe(
        customer_id=customer_id,
        payment_method_id=payment_method_id,
        amount_usd=1100.00,
        description="Sandbox test for industrial tool set",
        intent_id=intent_id,
    )
    print(result)

if __name__ == "__main__":
    main()
