window.onload=startup

function startup() {
    pipyinit()
    liveupdates()
}

function liveupdates() {
    var esource = new EventSource("dynupdates");
    esource.addEventListener("message", function(e) {
            if (e.data=='kwac') {
                console.log('nothing')
            } else {
                var newinfo=JSON.parse(e.data);
                newinfo.forEach(function(update, idx) {
                    console.log(update[0] + ' is ' + update[1]);
                    var tempel=document.getElementById(update[0]);
                    if (tempel) {
                        tempel.innerHTML=update[1];
                    }
                });
            }
        }, false);
    esource.addEventListener("open", function(e) {
            console.log('update conenction opened');
        }, false);
    esource.addEventListener("error", function(e) {
            if (e.readyState == EventSource.CLOSED) {
                console.log('update connection now closed');
            } else {
                console.log('update connection unhappy')
            }
        }, false);
}

function appUpload(inp) {
    var inff =document.getElementById(inp).files[0]
    var formData = new FormData();
    formData.append("stuff", inff);
    var req = new XMLHttpRequest();
    req.open("POST", 'setSettings');
    req.addEventListener("load", function () {
        window.location="";
    });
    req.addEventListener("error", function() {
        reportMessage('request failed')
    });
    req.addEventListener("abort", function() {
        reportMessage('request aborted')
    });
    req.send(formData);
}

function streamstatus() {
    var esource = new EventSource("streamstats");
    esource.addEventListener("message", function(e) {
            var newinfo=JSON.parse(e.data);
            Object.keys(newinfo).forEach(function(key) {
                var tempel=document.getElementById(key+'st');
                if (tempel) {
                    tempel.innerHTML=newinfo[key];
                }
            });

        }, false);
    esource.addEventListener("open", function(e) {
            var tempel = document.getElementById("appmessage");
            tempel.innerHTML="status Connection established";
        }, false);
    esource.addEventListener("error", function(e) {
            var tempel = document.getElementById("appmessage");
            if (e.readyState == EventSource.CLOSED) {
                tempel.innerHTML="status connection lost";
            } else {
                tempel.innerHTML="status connection had an error";
            }
        }, false);
}

function reportMessage(msg) {
    var rele=document.getElementById("appmessage")
    rele.innerHTML=msg
}

function appNotify(ele, ename) {
    var oReq = new XMLHttpRequest();
    oReq.addEventListener("load", function () {
        reportMessage(this.responseText)
    });
    oReq.addEventListener("error", function() {
        reportMessage('request failed')
    });
    oReq.addEventListener("abort", function() {
        reportMessage('request aborted')
    });
    oReq.open("GET", "updateSetting?t="+ele.id+"&v="+ele.value);
    oReq.send();
}

function smartNotify(ele, ename) {
    var oReq = new XMLHttpRequest();
    oReq.addEventListener("load", function () {
        var newval=JSON.parse(this.response);
        reportMessage(newval.msg);
        if ("innerHTML" in newval) {
            ele.innerHTML=newval.innerHTML;
        }
    });
    oReq.addEventListener("error", function() {
        reportMessage('request failed')
    });
    oReq.addEventListener("abort", function() {
        reportMessage('request aborted')
    });
    oReq.open("GET", "updateSetting?t="+ele.id+"&v="+ele.value);
    oReq.send();
}

function baseSmartNotify(ele, newvalue) {
    var oReq = new XMLHttpRequest();
    oReq.addEventListener("load", function () {
        var newval=JSON.parse(this.response);
        reportMessage(newval.msg);
        if ("innerHTML" in newval) {
            ele.innerHTML=newval.innerHTML;
        }
    });
    oReq.addEventListener("error", function() {
        reportMessage('request failed')
    });
    oReq.addEventListener("abort", function() {
        reportMessage('request aborted')
    });
    oReq.open("GET", "updateSetting?t="+ele.id+"&v="+newvalue);
    oReq.send();
}

function detstreamstart(ele) {
    dele=document.getElementById("detstreamdiv");
    dele.innerHTML='<img src="detstream.mjpg" id="detstreamimg"/>';
    dele.style.display="block";
}

function detstreamstop(ele) {
    var dele=document.getElementById("detstreamdiv");
    dele.style.display="none";
    dele.innerHTML=""
}

function livestreamstart(ele) {
    var dele=document.getElementById("livedivoff");
    dele.style.display="none";
    dele=document.getElementById("livestreamimg");
    dele.src="vstream.mjpg";
    dele=document.getElementById("livedivon");
    dele.style.display="block";
}

function livestreamstop(ele) {
    var dele=document.getElementById("livestreamimg");
    dele.src="nocam.png"
    dele=document.getElementById("livedivon");
    dele.style.display="none";
    dele=document.getElementById("livedivoff");
    dele.style.display="block";
}

function clickNotify(ele) {
    var oReq = new XMLHttpRequest();
    oReq.addEventListener("load", function () {
        console.log('update of field ' + ele.id + ' succeeded.');
        var newval=JSON.parse(this.response);
        if (ele.nodeName=='SPAN') {
            ele.innerHTML=newval
        }
        var cl = ele.classList;
        if (cl.contains("clicker1")) {
            cl.replace("clicker1","clicker0");
        }
        if (cl.contains("clickerpend")) {
            cl.remove("clickerpend");
        }
    }, false);
    oReq.addEventListener("error", function() {
        console.log('update of field ' + ele.id + ' failed.')
    }, false);
    oReq.addEventListener("abort", function() {
        console.log('update of field ' + ele.id + ' cancelled.')
    }, false);
    oReq.open("GET", "smartUpdate?t="+ele.id+"&v="+ele.value);
    oReq.send();
    var cl = ele.classList;
    if (cl.contains("clicker0")) {
        cl.replace("clicker0","clicker1");
    }
    if (cl.length==2) {
        cl.add("clickerpend");
    }    
}