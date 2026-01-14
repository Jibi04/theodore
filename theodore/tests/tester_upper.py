a_dict = {}

a_dict["Musa"] = "Yaradua"

def tryout():
    try:
        jupiter = str("this is not bytes")
        return 
    except Exception as e:
        print("Type of exception: ", type(e))
        print("Name of exception: ", type(e).__name__)


tryout()