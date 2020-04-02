
function pipyinit() {
    if (!!window.EventSource) {
        var tempdataset = new TimeSeries()
        var templine = new SmoothieChart({ fps: 30, millisPerPixel: 200, tooltip: false, minValue:20, maxValue:70,
                grid: { strokeStyle: '#555555', lineWidth: 1, millisPerLine: 5000, verticalSections: 4}});
        templine.addTimeSeries(tempdataset,
                { strokeStyle:'rgb(128, 250, 128)', fillStyle:'rgba(128, 250, 128, 0.4)', lineWidth:2 });
        templine.streamTo(document.getElementById("pitempchart"), 1000);
        var cpudataset = new TimeSeries();
        var cpudatasetavg = new TimeSeries();
        var cpudataavg = 0;
        var cpuchart = new SmoothieChart({ fps: 30, millisPerPixel: 200, tooltip: false, minValue:0, maxValue:100, 
                grid: { strokeStyle: '#555555', lineWidth: 1, millisPerLine: 5000, verticalSections: 4} });
        cpuchart.addTimeSeries(cpudataset,
                { strokeStyle:'rgb(128, 250, 128)', fillStyle:'rgba(128, 250, 128, 0.4)', lineWidth:2 });
        cpuchart.addTimeSeries(cpudatasetavg, 
                { strokeStyle:'rgb(250, 100, 128)', fillStyle:'rgba(250, 100, 128, 0.4)', lineWidth:2 });
        cpuchart.streamTo(document.getElementById("picputime"), 1000);
        var esource = new EventSource("pistatus?fields=busy&fields=cputemp");
        esource.addEventListener("message", function(e) {
            var newinfo=JSON.parse(e.data);
            tempdataset.append(Date.now(),newinfo.cputemp);
            cpudataset.append(Date.now(), newinfo.busy*100);
            cpudataavg=(cpudataavg*3+newinfo.busy*100)/4;
            cpudatasetavg.append(Date.now(),cpudataavg);
            var cel = document.getElementById("picpuavg");
            if (cel) {
                cel.innerHTML=cpudataavg.toFixed(2)+"%";
            }
        }, false);
        esource.addEventListener("open", function(e) {
            var tempel = document.getElementById("appmessage");
            tempel.innerHTML="update Connection established";
        }, false);
        esource.addEventListener("error", function(e) {
            var tempel = document.getElementById("appmessage");
            if (e.readyState == EventSource.CLOSED) {
                tempel.innerHTML="update connection lost";
            } else {
                tempel.innerHTML="update connection had an error";
            }
        }, false);
    } else {
        var tempel = document.getElementById("note");
        tempel.innerHTML="I'm sorry Dave, live updates not supported by this browser";
    }
}

function liveupdates(updatename) {
    var esource = new EventSource("updates?updatename="+updatename);
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
            console.log('update connection opened');
        }, false);
    esource.addEventListener("error", function(e) {
            if (e.readyState == EventSource.CLOSED) {
                console.log('update connection now closed');
            } else {
                console.log('update connection unhappy')
            }
        }, false);
}

async function appNotify(ele, pageid) {
    let response = await fetch("updateSetting?t="+ele.id+"&v="+ele.value+"&p="+pageid);
    if (response.ok) { // if HTTP-status is 200-299
        let resp = await response.text();
        if (resp!='OK ') {
            alert(resp)
        }
    } else {
        alert("HTTP-Error: " + response.status);
    }
}

function livestreamflip(btnel) {
    var imele=document.getElementById("livestreamimg");
    if (imele.src.endsWith("nocam.png")                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 ) {
        imele.src="camstream.mjpg"
        btnel.innerHTML="hide livestream"
    } else {
        imele.src="stat/nocam.png"
        btnel.innerHTML="show livestream"
    }
}

function detstreamflip(btnel) {
    var imele=document.getElementById("detstreamdiv");
    if (imele.style.display=="none") {
        imele.innerHTML='<img src="detstream.png" width = "640" height = "480" style="z-index:1;"/>';
        imele.style.display="block";
        btnel.innerHTML="hide detection"
    } else {
        imele.style.display="none";
        imele.innerHTML="";
        btnel.innerHTML="show detection"
    }
}

function maskeditflip(btnel) {
    var imele=document.getElementById("detstreamdiv");
}

function flipme(etag, itag) {
    var ele=document.getElementById(etag);
    var x=ele.style.display;
    var img=document.getElementById(itag);
    if (x=="none") {
        ele.style.display="";
        img.src="openuparrow.svg"
    } else {
        img.src="opendnarrow.svg"
        ele.style.display="none";
    }
}