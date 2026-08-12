SPACE_ID = "finance"
DATA_PRODUCT_ID = "sales"

SPACE_MEMBERSHIPS = {
    "alice": {
        "PK": "SPACE#finance",
        "SK": "MEMBER#alice",
        "userId": "alice",
        "role": "OWNER",
        "status": "ACTIVE",
    },
    "bob": {
        "PK": "SPACE#finance",
        "SK": "MEMBER#bob",
        "userId": "bob",
        "role": "DEPUTY",
        "status": "ACTIVE",
    },
    "charlie": {
        "PK": "SPACE#finance",
        "SK": "MEMBER#charlie",
        "userId": "charlie",
        "role": "PRODUCER",
        "status": "ACTIVE",
    },
    "david": {
        "PK": "SPACE#finance",
        "SK": "MEMBER#david",
        "userId": "david",
        "role": "CONSUMER",
        "status": "ACTIVE",
    },
}

DATA_PRODUCT_CONSUMERS = {
    ("emma", DATA_PRODUCT_ID): {
        "PK": "SPACE#finance",
        "SK": "DATAPRODUCT#sales#CONSUMER#emma",
        "userId": "emma",
        "dataProductId": "sales",
        "role": "CONSUMER",
        "status": "ACTIVE",
    }
}
