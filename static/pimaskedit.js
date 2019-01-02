var maskxstep;
var maskystep;
var celldownx;
var celldowny;

var lastcellx;
var lastcelly;

var maskcontext;
var maskcanvas;

var mouseisdown=0;
var maskadd=true;

var detectmask=null;

function editmaskstart(thisel) {
    if (thisel.innerHTML =='edit mask') {
        var oReq = new XMLHttpRequest();
        oReq.addEventListener("load", function () {
            var newval=JSON.parse(this.response);
            reportMessage(newval.msg);
            if ("mdata" in newval) {
                detectmask=newval.mdata
                doeditmask();
            } else {
                detectmask=[];
                for (var i=0;i<maskheight;i++) {
                    detectmask[i] = Array(maskwidth).fill(0);
                }
                doeditmask();
            }
        });
        oReq.addEventListener("error", function() {
            reportMessage('edit mask request failed')
        });
        oReq.addEventListener("abort", function() {
            reportMessage('edit mask request aborted')
        });
        oReq.open("GET", "fetchmask");
        oReq.send();
    } else {
        thisel.innerHTML = 'edit mask';
        var saveas=prompt("save changes as?");
        if (saveas != null && saveas != "") {
            var req = new XMLHttpRequest();
            req.open("POST", 'setdetectmask');
            req.addEventListener("load", function () {
                reportMessage(this.responseText)
            });
            req.addEventListener("error", function() {
                reportMessage('request failed')
            });
            req.addEventListener("abort", function() {
                reportMessage('request aborted')
            });
            req.setRequestHeader('Content-Type', 'application/json');
            req.send(JSON.stringify({
                'name': saveas,
                'mask': detectmask
            }));
        }
        var mdiv=document.getElementById("livemaskdiv");
        mdiv.style.display="none";
        detectmask=null;
        maskcontext=null;
    }
}

function doeditmask() {
    var thisel=document.getElementById('editmaskbtn')
    thisel.innerHTML = 'finish edit';
    var mdiv=document.getElementById("livemaskdiv")
    mdiv.style.display="block";
    var cstyle=getComputedStyle(mdiv);
    maskcanvas=document.getElementById("livemaskcanv")
    maskcontext=maskcanvas.getContext('2d');
    var cwidth=parseInt(cstyle.getPropertyValue('width'));
    var cheight= parseInt(cstyle.getPropertyValue('height'));
    maskcanvas.width = cwidth;
    maskcanvas.height = cheight;
    var maskwidth=64;
    var maskheight=48;
    maskcontext.lineWidth = 1;
    maskcontext.strokeStyle = '#00000080';
    var x;
    maskxstep=cwidth*1.0/maskwidth;
    for (x=0; x<maskwidth;x++) {
        maskcontext.beginPath();
        var xpos=maskxstep*x;
        maskcontext.moveTo(xpos, 0);
        maskcontext.lineTo(xpos, cheight-1);
        maskcontext.stroke();
    }
    maskystep=cheight*1.0/maskheight;
    for (x=0; x<maskheight;x++) {
        maskcontext.beginPath();
        var xpos=maskystep*x;
        maskcontext.moveTo(0, xpos);
        maskcontext.lineTo(cwidth-1, xpos);
        maskcontext.stroke();
    }
    for (x=0; x<maskwidth; x++) {
        for (var y=0; y<maskheight; y++) {
            if (detectmask[y][x]>0) {
                docell(x,y,true)
            }
        }
    }
    maskcanvas.addEventListener('mousedown', maskmousedown, false);
    maskcanvas.addEventListener('mousemove', maskmousemove, false);
    maskcanvas.addEventListener('mouseup', maskmouseup, false);
}

function maskmousedown(e) {
    celldownx = Math.floor(e.offsetX/maskxstep);
    celldowny = Math.floor(e.offsetY/maskxstep);
    lastcellx=celldownx;
    lastcelly=celldowny;
    maskadd=!e.shiftKey;
    docell(celldownx, celldowny, maskadd);
    mouseisdown=1;
}

function maskmousemove(e) {
    if (mouseisdown) {
        var newdownx = Math.floor(e.offsetX/maskxstep);
        var newdowny = Math.floor(e.offsetY/maskxstep);
        if ((newdownx != lastcellx) || (newdowny != lastcelly)) {
            var xbase=celldownx;
            var xlim =lastcellx;
            if (xlim < xbase) {
                xbase=xlim;
                xlim =celldownx;
            }
            var ybase=celldowny;
            var ylim =lastcelly;
            if (ylim < ybase) {
                ybase=ylim;
                ylim=celldowny;
            }
            for (var x=xbase; x <= xlim; x++) {
                for (var y=ybase; y <= ylim; y++) {
                    docell(x,y,false);
                }
            }
            if (maskadd) {
                xbase=celldownx;
                xlim =newdownx;
                if (xlim < xbase) {
                    xbase=xlim;
                    xlim =celldownx;
                }
                var ybase=celldowny;
                var ylim =newdowny;
                if (ylim < ybase) {
                    ybase=ylim;
                    ylim=celldowny;
                }
                var x;
                var y;
                for (x=xbase; x <= xlim; x++) {
                    for (y=ybase; y <= ylim; y++) {
                        docell(x,y,true);
                    }
                }
            }
            lastcellx=newdownx;
            lastcelly=newdowny;
        }       
    }
}

function maskmouseup(e) {
    mouseisdown=0
}

function docell(cellx, celly, cellon) {
    maskcontext.clearRect(cellx*maskxstep+1, celly*maskystep+1, maskxstep-2, maskystep-2)
    if (cellon) {
        maskcontext.fillStyle = '#0000c070';
        maskcontext.fillRect(cellx*maskxstep+1, celly*maskystep+1, maskxstep-2, maskystep-2);
    }
    var cellval=0;
    if (cellon) {
        cellval=1;
    }
    detectmask[celly][cellx]=cellval;
}