const choice = list => list[Math.floor(Math.random()*list.length)];

const getRandomVoiceId = (languageCode, voices) => {
    const [language, country] = languageCode.split("-");
    const fullVoiceList = voices[language];
    
    if(country){
        const filteredByCountry = voices[language].filter(x => x.FullLanguageCode === languageCode);
        return choice(filteredByCountry)
    }
    return choice(fullVoiceList);
    
}

const getUrlFromEvent = ({body}) => {
    let bodyJ = {};
    try{
        bodyJ = JSON.parse(body);
    }catch(error){
        return null;
    }
    
    return bodyJ.Url;
}

                                    
const getDominantLanguage = 
    ({Languages}) => Languages.sort((a,b) => b['Score'] - a['Score'])[0];

module.exports = {
    choice,
    getRandomVoiceId,
    getUrlFromEvent,
    getDominantLanguage
};