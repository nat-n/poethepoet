def detect_poe_test_package():
    try:
        import poe_test_package

        print("poe_test_package found at", poe_test_package.__file__)
    except:
        print("No poe_test_package found")
