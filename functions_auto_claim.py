import pyodbc
from decimal import Decimal

# Azure SQL Server connection parameters (auto-claim database)
#SERVER = "auto-claim-server.database.windows.net"
_SERVER = "hcvwtdbasql2"
_DATABASE = "auto_claim"
_USERNAME = "sqladmin"
_PASSWORD = "Passw0rd"

# Candidate ODBC drivers, newest first - the first installed one is used for azure sql and local sql server connection
_DRIVERS = [
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "ODBC Driver 13 for SQL Server",
]

_AUTO_CLAIM_QUERY = """
SELECT
    c.CustomerID,
    c.FirstName,
    c.LastName,
    SUM(ISNULL(cl.ClaimAmount,0)) AS TotalClaimAmount
FROM dbo.Customer c
LEFT JOIN dbo.Policy p
    ON c.CustomerID = p.CustomerID
LEFT JOIN dbo.Claim cl
    ON p.PolicyID = cl.PolicyID
GROUP BY
    c.CustomerID,
    c.FirstName,
    c.LastName
HAVING
    SUM(ISNULL(cl.ClaimAmount,0)) > ?
ORDER BY
    TotalClaimAmount DESC;
"""

# {where_clause} is replaced with 'WHERE c.CustomerID IN (...)' when the
# detail query is called with a list of customer IDs.
_AUTO_CLAIM_DETAIL_QUERY = """
SELECT
    c.CustomerID,
    c.FirstName,
    c.LastName,
    p.PolicyNumber,
    p.VehicleMake,
    p.VehicleModel,
    cl.ClaimNumber,
    cl.ClaimStatus,
    cl.ClaimAmount
FROM dbo.Customer c
LEFT JOIN dbo.Policy p
    ON c.CustomerID = p.CustomerID
LEFT JOIN dbo.Claim cl
    ON p.PolicyID = cl.PolicyID
{where_clause}
ORDER BY
    c.CustomerID,
    p.PolicyID,
    cl.ClaimID;
"""


def _get_driver() -> str:
    """Return the first installed SQL Server ODBC driver from the candidate list."""
    available = pyodbc.drivers()
    for candidate in _DRIVERS:
        if candidate in available:
            return candidate
    raise RuntimeError(
        "No SQL Server ODBC driver found. Install the Microsoft ODBC Driver for "
        f"SQL Server. Detected drivers: {available}"
    )


def _connection_string() -> str:
    """Build the pyodbc connection string for the auto-claim Azure SQL Server."""
    return (
        "DRIVER={{{driver}}};"
        "SERVER={server};"
        "DATABASE={database};"
        "UID={username};"
        "PWD={password};"
        "Encrypt=yes;"
#        "TrustServerCertificate=no;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=30;"
    ).format(
        driver=_get_driver(),
        server=_SERVER,
        database=_DATABASE,
        username=_USERNAME,
        password=_PASSWORD,
    )


def _rows_to_dicts(cursor) -> list:
    """Convert all fetched rows to dicts, casting SQL Decimal to float."""
    columns = [column[0] for column in cursor.description]
    rows = []
    for row in cursor.fetchall():
        row_dict = dict(zip(columns, row))
        # SQL Server returns Decimal for money/numeric columns,
        # which is not JSON-serializable - convert to float.
        rows.append(
            {
                key: float(value) if isinstance(value, Decimal) else value
                for key, value in row_dict.items()
            }
        )
    return rows


def auto_claim_query(threshold: float = 10000.0) -> dict:
    """
    Query Azure SQL Server 'auto_claim' for customers whose total claim amount
    exceeds the given threshold.

    Args:
        threshold: The claim amount threshold to filter customers by. Only
            customers with total claim amount GREATER than this value are
            returned. Defaults to 10000.0.

    Returns:
        dict: Always a dict. On success it contains 'status', 'count' and a
        'customers' list of dicts with the found CustomerID, FirstName,
        LastName and TotalClaimAmount. On error it contains 'status' and
        'message'.
    """
    try:
        with pyodbc.connect(_connection_string()) as conn:
            with conn.cursor() as cursor:
                cursor.execute(_AUTO_CLAIM_QUERY, (threshold,))
                customers = _rows_to_dicts(cursor)

        return {
            "status": "Success",
            "count": len(customers),
            "customers": customers,
        }
    except pyodbc.Error as e:
        return {"status": "Error", "message": f"Database connection/query error: {str(e)}"}
    except Exception as e:
        return {"status": "Error", "message": f"Failed to query auto-claim data: {str(e)}"}


def auto_claim_detail_query(customer_ids: list) -> dict:
    """
    Query Azure SQL Server 'auto_claim' for the full policy/claim detail of the
    given high-value customers (typically the CustomerIDs returned by
    auto_claim_query).

    Args:
        customer_ids: List of CustomerIDs to filter on, e.g. [1, 2].

    Returns:
        dict: Always a dict. On success it contains 'status', 'count' and a
        'details' list of dicts with CustomerID, FirstName, LastName,
        PolicyNumber, VehicleMake, VehicleModel, ClaimNumber, ClaimStatus and
        ClaimAmount. On error it contains 'status' and 'message'.
    """
    if not customer_ids:
        return {"status": "Error", "message": "customer_ids must be a non-empty list of CustomerIDs."}

    # Parameterized IN clause: one '?' placeholder per customer ID
    placeholders = ", ".join("?" for _ in customer_ids)
    query = _AUTO_CLAIM_DETAIL_QUERY.format(
        where_clause=f"WHERE c.CustomerID IN ({placeholders})"
    )

    try:
        with pyodbc.connect(_connection_string()) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, tuple(customer_ids))
                details = _rows_to_dicts(cursor)

        return {
            "status": "Success",
            "count": len(details),
            "details": details,
        }
    except pyodbc.Error as e:
        return {"status": "Error", "message": f"Database connection/query error: {str(e)}"}
    except Exception as e:
        return {"status": "Error", "message": f"Failed to query auto-claim detail: {str(e)}"}