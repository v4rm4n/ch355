# - ch355/api/utils.py -

def response(data = None, message: str = "", code: int = 200):
    return {
        "status": "success" if code < 400 else "error",
        "code": code,
        "message": message,
        "data": data
    }