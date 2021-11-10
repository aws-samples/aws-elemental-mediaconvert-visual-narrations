const {secondsToSMPTEString} = require('./SMPTE');

const makeSRTItem = (index, start, end, title) => 
`${index}
${start} --> ${end}
${title}

`;

const makeSRTFile = (titles, duration) => {
    if(!titles?.length){
        return null;
    }
    
    const segmentDurationInSec = duration / titles.length;
    const delta = 0.1;
    const segments = Array(titles.length).fill(segmentDurationInSec).map(
        (current, index) => ([
            index+1,
            secondsToSMPTEString(current*index + delta),
            secondsToSMPTEString(current*(index+1)),
            titles[index]
        ])
    );
    
    return segments
            .map(item => makeSRTItem( ... item))
            .reduce((memo, next) => memo + next, "");
}

module.exports = {
    makeSRTFile
};