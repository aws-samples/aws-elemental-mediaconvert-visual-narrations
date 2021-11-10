/** Convert seconds to SMPTE timecode JSON object, example input is html video.currentTime */
function secondsToSMPTE(seconds, framerate=1000) {
    var f = Math.floor((seconds % 1) * framerate);
    var s = Math.floor(seconds);
    var m = Math.floor(s / 60);
    var h = Math.floor(m / 60);
    m = m % 60;
    s = s % 60;

    return {h: h, m: m, s: s, f: f};
}

/** Pretty print SMPTE timecode JSON object */
function SMPTEToString(timecode) {
    if (timecode.h < 10) { timecode.h = "0" + timecode.h; }
    if (timecode.m < 10) { timecode.m = "0" + timecode.m; }
    if (timecode.s < 10) { timecode.s = "0" + timecode.s; }
    let f = timecode.f;
    if(timecode.f < 100){
        f = "0" + timecode.f
    }
    if (timecode.f < 10) {
        f = "00" + timecode.f;
    }

    return timecode.h + ":" + timecode.m + ":" + timecode.s + "," + f;
}

function secondsToSMPTEString(seconds, framerate=1000){
    return SMPTEToString(
        secondsToSMPTE(seconds, framerate)
    );
}

module.exports = {
    secondsToSMPTEString
};