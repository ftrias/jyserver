/*
This is the Javascript code that gets injected into the HTML
page.

server            Proxy class for asynchronous execution of commands
                  on the server. This class does not return a value.

app               Proxy class that for synchronous exection. Will
                  return a value. However, if used while a page
                  update is in progress, it will fail.

Other functions used internally:

evalBrowser()     Queries the server for any pending commands. If
                  there are no pending commands, the connection
                  is kept open by the server until a pending
                  command is issued, or a timeout. At the end of
                  the query, the function gets scheduled for execution
                  again. We schedule it instead of calling so we
                  don't overflow the stack.

sendFromBrowserToServer(e, q) 
                  Evaluate expression `e` and then send the results
                  to the server. This is used by the server to
                  resolve Javascript statements.

sendErrorToServer(e)
                  Send a client expcetion to the server for error
                  handling.

closeBrowserWindow()
                  Called when a page is terminated so server can
                  stop processing it.
*/

    if (typeof UID === "undefined") { UID = "COOKIE"; }
    if (typeof PAGEID === "undefined") { PAGEID = "COOKIE"; }
    function evalBrowser() {
        var request = new XMLHttpRequest();
        request.onreadystatechange = function() {
            if (request.readyState==4 && request.status==200){
                try {
                    //console.log("Next async task", request.responseText) // DEBUG
                    eval(request.responseText)
                    //console.log("Done")
                    setTimeout(evalBrowser, 1);
                }
                catch(e) {
                    console.log("ERROR", e.message) // DEBUG
                    setTimeout(function(){sendErrorToServer(request.responseText, e.message); evalBrowser();}, 1);
                }
            }
        }
        request.open("POST", "/_process_srv0");
        request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        request.send(JSON.stringify({"session": PAGEID, "task":"next"}));
        //console.log("Query next commands") // DEBUG
    }
    function sendFromBrowserToServer(expression, query) {
        var value
        var error = ""
        try {
            //console.log("Evaluate", query, expression) // DEBUG
            value = eval(expression)
            //console.log("Result", value)
        }
        catch (e) {
            value = 0
            error = e.message + ": '" + expression + "'"
            console.log("ERROR", query, error)
        }
        var request = new XMLHttpRequest();
        request.open("POST", "/_process_srv0");
        request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        request.send(JSON.stringify({"session":PAGEID, "task":"state", "value":value, "query":query, "error": error}));
        //console.log("response",value) // DEBUG
    }
    function sendErrorToServer(expr, e) {
        var request = new XMLHttpRequest();
        request.open("POST", "/_process_srv0");
        request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        request.send(JSON.stringify( {"session":PAGEID, "task":"error", "error":e, "expr":expr} ));
    }
    function closeBrowserWindow() {
        var request = new XMLHttpRequest();
        request.open("POST", "/_process_srv0");
        request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        request.send(JSON.stringify({"session":PAGEID, "task":"unload"}));
    }
    server = new Proxy({}, { 
        get : function(target, property) { 
            return function(...args) {
                var request = new XMLHttpRequest();
                request.onreadystatechange = function() {
                    if (request.readyState==4 && request.status==200){
                        result = JSON.parse(request.responseText)
                        if ("error" in result) {
                            console.log("ERROR async: ", property, request.responseText)
                            throw result["error"]
                        }
                    }
                }
                request.open("POST", "/_process_srv0");
                request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
                request.send(JSON.stringify({"session":PAGEID, "task":"async", "function":property, "args":args}));
                //console.log("send asynch",property,args) // DEBUG
            }            
        }
    });
    function handleApp(property, args) { 
        var request = new XMLHttpRequest();
        request.open("POST", "/_process_srv0", false);
        request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        request.send(JSON.stringify({"session":PAGEID, "task":"run", "block":true, "function":property, "args":args}));
        if (request.status === 200) {
            var result = JSON.parse(request.responseText)
            if ("error" in result) {
                console.log("ERROR", result["error"]);
                throw result["error"];
                // return null;
            }
            if (result["type"] == "expression") {
                return eval(result["expression"])
            }
            else {
                return result["value"]
            }
        }
    }
    function handleAppProperty(property) { 
        var request = new XMLHttpRequest();
        request.open("POST", "/_process_srv0", false);
        request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        request.send(JSON.stringify({"session":PAGEID, "task":"get", "block":true, "expression":property}));
        if (request.status === 200) {
            var result = JSON.parse(request.responseText)
            if ("error" in result) {
                console.log("ERROR", result["error"]);
                throw result["error"];
                // return null;
            }
            if (result["type"] == "expression") {
                return eval(result["expression"])
            }
            else {
                return result["value"]
            }
        }
    }
    function handleAppSetProperty(property, value) { 
        var request = new XMLHttpRequest();
        request.open("POST", "/_process_srv0", false);
        request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        request.send(JSON.stringify({"session":PAGEID, "task":"set", "property":property, "value":value}));
        return value
    }
    app = new Proxy({}, { 
        get : function(target, prop) { 
            return handleAppProperty(prop)
        },
        set : function(target, prop, value) { 
            return handleAppSetProperty(prop, value)
        }
    });
    window.addEventListener("beforeunload", function(event) { closeBrowserWindow(); });
    window.addEventListener("load", function(event) { evalBrowser(); });