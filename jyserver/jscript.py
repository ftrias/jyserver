import os
dir = os.path.dirname(__file__)
with open(dir + "/jyserver-min.js", "rb") as f:
    JSCRIPT = f.read()