client_secret = {
    "client_id": "ABNihhsjY5DjSU7fzatOem89QT7PB0PCSQigLnKxSshOmk4KAy",
    "client_secret": "JScyUfsuob1feuQ0PzCLHpemPVN4Zgx1qNTma311",
    "redirect_uri": "https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl",
    "environment": "production",
}
qBData = {
    "realm_id": "9130349871157926",
    "accessToken": "eyJlbmMiOiJBMTI4Q0JDLUhTMjU2IiwiYWxnIjoiZGlyIn0..PZsKojYbfi5Q4Y0YNT3-xg.q-8iAMdA4x_l-WAcUhaamx80pRXdYvX1_SfblrsG8mU1Ex9hiaPNWTvMsGg18yCfwX0sQb8Caq4hnbL_S_cPwVNPESERa_S64xU2gPqj7WAC1yEs-TO1Nb5zsycJnqBX7hqw1Rv6nrVMWXRaZIIBsRjVnh4YWIhGRFp7PRon7wKqRwm5kgZU1tKo6Ggrj1aEEP3EhIqQdjfQKxkNaJHQT9_J6ZXWsfPMDyl1to11stP00owV_8qKGCMCy-jEed3XTFczAHozUYxGMzoSxCrWewPYVPXTapyok3kfE9pkYi_b2buL74yltAWxZpzHKHKK0qFqpkWDmHeTXFeuWhtaB4i3K0kTrJU4bG9c3DiK2u2Yz2BFk6YR4BdYbQ7hlpdOPnRi6cJXBLs9TqnmbKU5pepbtvy-djiADSVIJZtYSHpOZGTaP84vHtTfqlRPiD6lq1LrclTlQFQJn3QzAy0g28c3hkNyfV-ucv6fhAX9pxiIMCamO53kbec-VIJeuk4cOqh3OcXqLfXEXJY9TwH889xFPS7w8IV0WM4i6vNvb2WY4qyIS-x-1a4Ah6nkDM6BhbAbaJthK_Wkn1jk9Kx91swxMgtp-uAtrvC1bevrRBgVYPGAdMKeV4pSiL0zqu7Heu1B0Safqrr1JXeH3OKjEmlDN_lUfM5GUTVQYBFVhL18m9kEw4kmIYuHsvSEdrfiegb05fhwzOhHCNzRXgK6zUVRsbOS_TAYD2ooyulvbNu2RXyCdPBuBlHncQO1TIfC.QKDOERphQtzToRLIohUdxA",
}

auth_headers = {"Auth": "6dfcfe785d48a0aaa29cb4d0e7beb7df"}

sellercloud_credentials = {
    "Username": "aborroto@krameramerica.com",
    "Password": "Ab10037659!!",
}

sellercloud_base_url = "https://krameramerica.api.sellercloud.us/rest/api/"
sellercloud_endpoints = {
    "GET_TOKEN": {
        "type": "post",
        "url": sellercloud_base_url + "token",
        "endpoint_error_message": "while getting SellerCoud API access token: ",
        "success_message": "Got SellerCloud API access token successfully!",
    },
    "GET_ORDERS": {
        "type": "get",
        "url": sellercloud_base_url + "Orders/{order_id}",
        "endpoint_error_message": "while getting order from SellerCloud: ",
        "success_message": "Got an order successfully!",
    },
    "GET_CUSTOMER": {
        "type": "get",
        "url": sellercloud_base_url + "Customers/{id}",
        "endpoint_error_message": "while getting customer from SellerCloud: ",
        "success_message": "Got an customer successfully!",
    },
}

db_config = {
    "AmazonVendor": {
        "server": "krameramerica.database.windows.net",
        "database": "AmazonVendor",
        "username": "aborroto",
        "password": "KramerAmerica4321!",
        "driver": "{ODBC Driver 17 for SQL Server}",
    },
    "ProductCatalog": {
        "server": "krameramerica.database.windows.net",
        "database": "ProductCatalog",
        "username": "aborroto",
        "password": "KramerAmerica4321!",
        "driver": "{ODBC Driver 17 for SQL Server}",
    },
    "DropshipSellerCloud": {
        "server": "krameramerica.database.windows.net",
        "database": "DropshipSellerCloud",
        "username": "aborroto",
        "password": "KramerAmerica4321!",
        "driver": "{ODBC Driver 17 for SQL Server}",
    },
    "DropshipSellerCloudTest": {
        "server": "krameramerica.database.windows.net",
        "database": "DropshipSellerCloudTest",
        "username": "aborroto",
        "password": "KramerAmerica4321!",
        "driver": "{ODBC Driver 17 for SQL Server}",
    },
    "QuickBooks": {
        "server": "krameramerica.database.windows.net",
        "database": "Quickbooks",
        "username": "dan123",
        "password": "Pokemon07!",
        "driver": "{ODBC Driver 17 for SQL Server}",
    },
    "ProcessLogs": {
        "server": "krameramerica.database.windows.net",
        "database": "ProcessLogs",
        "username": "aborroto",
        "password": "KramerAmerica4321!",
        "driver": "{ODBC Driver 17 for SQL Server}",
    },
}


def create_connection_string(server_config):
    return (
        f"DRIVER={server_config['driver']};"
        f"SERVER={server_config['server']};"
        f"PORT=1433;DATABASE={server_config['database']};"
        f"UID={server_config['username']};"
        f"PWD={server_config['password']}"
    )


ftp_server = {
    "server": "krameramerica.exavault.com",
    "dguardado": {
        "user": "dguardado",
        "password": "Pokemon07!!",
    },
    "aborroto": {
        "user": "aborroto",
        "password": "Ab10037659!",
    },
}

SENDER_EMAIL = "logs@krameramerica.com"
SENDER_PASSWORD = "KramerAmerica2021"
RECIPIENT_EMAILS = ["itdepartment@krameramerica.com"]
