const targetScore = score => item => item.Score >= score;
const targetTypes = types => item => types.includes(item.Type);
const textLens = item => item?.Text;
const setReducer = (memo, next) => memo.add(next);
const stringReducer = (memo, next) => memo += `${next};`;

const VMAPBody = ADS_URL =>
`<?xml version="1.0" encoding="UTF-8"?>
<vmap:VMAP xmlns:vmap="http://www.iab.net/videosuite/vmap"version="1.0">
    <vmap:AdBreak timeOffset="start"breakType="linear" breakId="pre">
        <vmap:AdSource id="ad-source-1"followRedirects="true">
            <vmap:AdTagURI templateType="vast3">
                <![CDATA[ ${ADS_URL} ]]>
            </vmap:AdTagURI>
        </vmap:AdSource>
    </vmap:AdBreak>
    <vmap:AdBreak timeOffset="end" breakType="linear" breakId="post">
        <vmap:AdSource id="ad-source-1"followRedirects="true">
            <vmap:AdTagURI templateType="vast3">
                <![CDATA[ ${ADS_URL} ]]>
            </vmap:AdTagURI>
        </vmap:AdSource>
    </vmap:AdBreak>
</vmap:VMAP>`;

const allowedTypes = [
    "ORGANIZATION"
];

const getKeywordsFromEntities = 
    entities => 
        entities.filter(targetScore(0.80))
                .filter(targetTypes(allowedTypes))
                .map(textLens)
                .reduce(setReducer, new Set())

const getKeywordsFromEntitiesString =
entities =>
    Array.from(getKeywordsFromEntities(entities))
    .reduce(stringReducer)



module.exports = {
    VMAPBody,
    getKeywordsFromEntities,
    getKeywordsFromEntitiesString
};