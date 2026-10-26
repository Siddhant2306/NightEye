TEST_SIZE = 0.20

def split_data(data, feature_cols):
    split_idx = int(len(data) * (1 - TEST_SIZE))
    test_start_date = data.index[split_idx]

    # Do not train on a label whose outcome falls in the test period.
    train = data[data["target_date"] < test_start_date]
    test = data[data.index >= test_start_date]

    if len(train) == 0 or len(test) == 0:
        raise ValueError("Not enough rows to create train/test sets.")

    X_train = train[feature_cols]
    y_train = train["target"]

    X_test = test[feature_cols]
    y_test = test["target"]

    print(f"\nTraining observations: {len(train)}")
    print(f"Testing observations:  {len(test)}")
    print(f"Test period starts:    {test_start_date.date()}")

    return X_train, y_train, X_test, y_test, test