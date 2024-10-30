from app import app
import re
ptn = r'([a-zA-Z])+$'
size = re.search(ptn,"Abigail S")
print (size[0])

