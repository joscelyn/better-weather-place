export const supportedLanguages = ["en", "fr", "es", "de", "it"] as const;

export type Language = typeof supportedLanguages[number];

type LayerTranslation = {
  label: string;
  shortLabel: string;
  unit: string;
  source: string;
  resolution: string;
};

type Translation = {
  locale: string;
  metaDescription: string;
  months: readonly string[];
  layers: Record<string, LayerTranslation>;
  ui: {
    climateMap: string;
    zoomIn: string;
    zoomOut: string;
    climateDataChoice: string;
    display: string;
    rainyDays: string;
    compositeScore: string;
    intensity: string;
    climateLayerIntensity: string;
    learnMore: string;
    methodSourcesScore: string;
    aboutLabel: string;
    legend: string;
    hoveredPointData: string;
    updatingData: string;
    hoverData: string;
    exploreMap: string;
    hoverHint: string;
    monthlyNormals: string;
    readingData: string;
    unavailable: string;
    monthChoice: string;
    previousMonth: string;
    nextMonth: string;
    mapLoading: string;
    resourceError: string;
    loading: string;
    mapSourcesLabel: string;
    closeSources: string;
    mapAndData: string;
    sourcesAndAttributions: string;
    sourcesDescription: string;
    climateData: string;
    baseMap: string;
    geographicData: string;
    osmContributors: string;
    terrain: string;
    terrainProvider: string;
    closeAbout: string;
    aboutTitle: string;
    aboutBeforeLink: string;
    openSourceMap: string;
    aboutAfterLink: string;
    scoring: string;
    scoringDescription: string;
    scoreComposition: string;
    day: string;
    dayIdeal: string;
    night: string;
    nightIdeal: string;
    sun: string;
    sunIdeal: string;
    rain: string;
    rainIdeal: string;
    scoreDetail: string;
    dataAndMethod: string;
    temperatureSourceDetail: string;
    sunshineSourceDetail: string;
    normalsDetail: string;
    openGithub: string;
    language: string;
  };
};

const sharedLayerValues = {
  temperatureUnit: "°C",
  comfortUnit: "score%",
};

export const languageNames: Record<Language, string> = {
  en: "English",
  fr: "Français",
  es: "Español",
  de: "Deutsch",
  it: "Italiano",
};

export const translations: Record<Language, Translation> = {
  en: {
    locale: "en-GB",
    metaDescription: "Explore monthly climate normals for 1991–2020 across Europe and the Mediterranean.",
    months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    layers: {
      comfort: { label: "Weather score", shortLabel: "Weather score", unit: sharedLayerValues.comfortUnit, source: "CHELSA + SARAH-3 composite score", resolution: "about 5 km" },
      tavg: { label: "Average temperature", shortLabel: "Temperature", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "about 1 km" },
      tmax: { label: "Daytime temperature", shortLabel: "Day", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "about 1 km" },
      tmin: { label: "Night-time temperature", shortLabel: "Night", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "about 1 km" },
      precipitation: { label: "Monthly precipitation", shortLabel: "Total rain", unit: "mm/month", source: "CHELSA-monthly V2.1", resolution: "about 1 km" },
      sunshine: { label: "Sunshine duration", shortLabel: "Sunshine", unit: "h/month", source: "SARAH-3 (up to 65° N)", resolution: "about 5 km" },
    },
    ui: {
      climateMap: "Interactive climate map", zoomIn: "Zoom in", zoomOut: "Zoom out", climateDataChoice: "Choose climate data", display: "Display", rainyDays: "Rainy days", compositeScore: "Composite score", intensity: "Intensity", climateLayerIntensity: "Climate layer intensity", learnMore: "Learn more", methodSourcesScore: "Method, sources and weather score", aboutLabel: "About Better Weather Place", legend: "Legend", hoveredPointData: "Climate data for the hovered point", updatingData: "Updating data", hoverData: "Hover data", exploreMap: "Explore the map", hoverHint: "Hover over the map to compare the weather indicators for this location.", monthlyNormals: "Monthly normals 1991–2020", readingData: "Reading data…", unavailable: "N/A", monthChoice: "Choose a month", previousMonth: "Previous month", nextMonth: "Next month", mapLoading: "Loading map…", resourceError: "A map resource failed to load", loading: "Loading", mapSourcesLabel: "Map sources and attributions", closeSources: "Close sources and attributions", mapAndData: "Map and data", sourcesAndAttributions: "Sources and attributions", sourcesDescription: "Sources of climate, geographic and map data.", climateData: "Climate data", baseMap: "Base map", geographicData: "Geographic data", osmContributors: "© OpenStreetMap contributors", terrain: "Terrain", terrainProvider: "Mapzen Terrain Tiles on AWS", closeAbout: "Close the About dialog", aboutTitle: "Find the best weather compromise", aboutBeforeLink: "Better Weather Place is an", openSourceMap: "open-source map", aboutAfterLink: "that lets you explore, month by month, the regions with the most pleasant living conditions based on different climate criteria.", scoring: "Scoring", scoringDescription: "The monthly weather score ranges from 0 to 100. It combines four criteria using a geometric mean, so a very poor result cannot be fully offset by the others.", scoreComposition: "Weather score composition", day: "Day", dayIdeal: "ideal between 22 and 27 °C", night: "Night", nightIdeal: "ideal between 12 and 18 °C", sun: "Sunshine", sunIdeal: "ideal between 6 and 9 h/day", rain: "Rain", rainIdeal: "lower totals are favoured", scoreDetail: "Deviations are progressively penalised on both sides, with an additional penalty when high heat and strong sunshine coincide. This score is a general comfort indicator, not a forecast or medical advice.", dataAndMethod: "Data and method", temperatureSourceDetail: "temperatures and precipitation, about 1 km.", sunshineSourceDetail: "sunshine duration, about 5 km and up to 65° N.", normalsDetail: "Monthly climate normals for 1991–2020; score resolution: about 5 km.", openGithub: "Open GitHub", language: "Language",
    },
  },
  fr: {
    locale: "fr-FR",
    metaDescription: "Explorez les normales climatiques mensuelles 1991–2020 en Europe et autour de la Méditerranée.",
    months: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
    layers: {
      comfort: { label: "Score météo", shortLabel: "Score météo", unit: sharedLayerValues.comfortUnit, source: "Score composite CHELSA + SARAH-3", resolution: "environ 5 km" },
      tavg: { label: "Température moyenne", shortLabel: "Température", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "environ 1 km" },
      tmax: { label: "Température de jour", shortLabel: "Jour", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "environ 1 km" },
      tmin: { label: "Température de nuit", shortLabel: "Nuit", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "environ 1 km" },
      precipitation: { label: "Précipitations mensuelles", shortLabel: "Pluie totale", unit: "mm/mois", source: "CHELSA-monthly V2.1", resolution: "environ 1 km" },
      sunshine: { label: "Durée d’ensoleillement", shortLabel: "Soleil", unit: "h/mois", source: "SARAH-3 (jusqu’à 65° N)", resolution: "environ 5 km" },
    },
    ui: {
      climateMap: "Carte climatique interactive", zoomIn: "Zoom avant", zoomOut: "Zoom arrière", climateDataChoice: "Choix de la donnée climatique", display: "Afficher", rainyDays: "Jours de pluie", compositeScore: "Score composite", intensity: "Intensité", climateLayerIntensity: "Intensité de la couche climatique", learnMore: "En savoir plus", methodSourcesScore: "Méthode, sources et score météo", aboutLabel: "À propos de Better Weather Place", legend: "Légende", hoveredPointData: "Données climatiques du point survolé", updatingData: "Mise à jour des données", hoverData: "Données au survol", exploreMap: "Explorer la carte", hoverHint: "Survolez la carte pour comparer les indicateurs météo de ce lieu.", monthlyNormals: "Normales mensuelles 1991–2020", readingData: "Lecture des données…", unavailable: "N/D", monthChoice: "Choix du mois", previousMonth: "Mois précédent", nextMonth: "Mois suivant", mapLoading: "Chargement de la carte…", resourceError: "Une ressource cartographique n’a pas chargé", loading: "Chargement", mapSourcesLabel: "Sources et attributions de la carte", closeSources: "Fermer les sources et attributions", mapAndData: "Carte et données", sourcesAndAttributions: "Sources et attributions", sourcesDescription: "Origine des données climatiques, géographiques et cartographiques.", climateData: "Données climatiques", baseMap: "Fond de carte", geographicData: "Données géographiques", osmContributors: "© contributeurs OpenStreetMap", terrain: "Relief", terrainProvider: "Mapzen Terrain Tiles sur AWS", closeAbout: "Fermer la fenêtre À propos", aboutTitle: "Trouver le meilleur compromis météo", aboutBeforeLink: "Better Weather Place est une", openSourceMap: "carte open source", aboutAfterLink: "qui permet de visualiser, mois par mois, les régions où il fait bon vivre selon différents critères climatiques.", scoring: "Scoring", scoringDescription: "Le score météo mensuel va de 0 à 100. Il combine quatre critères avec une moyenne géométrique : un très mauvais résultat ne peut donc pas être entièrement compensé par les autres.", scoreComposition: "Composition du score météo", day: "Jour", dayIdeal: "idéal entre 22 et 27 °C", night: "Nuit", nightIdeal: "idéale entre 12 et 18 °C", sun: "Soleil", sunIdeal: "idéal entre 6 et 9 h/jour", rain: "Pluie", rainIdeal: "faible cumul favorisé", scoreDetail: "Les écarts sont pénalisés progressivement des deux côtés, avec une pénalité supplémentaire lorsque forte chaleur et fort soleil se cumulent. Ce score est un repère de confort général, pas une prévision ni un conseil médical.", dataAndMethod: "Données et méthode", temperatureSourceDetail: "températures et précipitations, environ 1 km.", sunshineSourceDetail: "durée d’ensoleillement, environ 5 km et jusqu’à 65° N.", normalsDetail: "Normales climatiques mensuelles 1991–2020 ; résolution du score : environ 5 km.", openGithub: "Ouvrir GitHub", language: "Langue",
    },
  },
  es: {
    locale: "es-ES",
    metaDescription: "Explora las normales climáticas mensuales de 1991–2020 en Europa y el Mediterráneo.",
    months: ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"],
    layers: {
      comfort: { label: "Puntuación meteorológica", shortLabel: "Puntuación", unit: sharedLayerValues.comfortUnit, source: "Puntuación compuesta CHELSA + SARAH-3", resolution: "unos 5 km" },
      tavg: { label: "Temperatura media", shortLabel: "Temperatura", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "aprox. 1 km" },
      tmax: { label: "Temperatura diurna", shortLabel: "Día", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "aprox. 1 km" },
      tmin: { label: "Temperatura nocturna", shortLabel: "Noche", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "aprox. 1 km" },
      precipitation: { label: "Precipitación mensual", shortLabel: "Lluvia total", unit: "mm/mes", source: "CHELSA-monthly V2.1", resolution: "aprox. 1 km" },
      sunshine: { label: "Duración de la insolación", shortLabel: "Sol", unit: "h/mes", source: "SARAH-3 (hasta 65° N)", resolution: "unos 5 km" },
    },
    ui: {
      climateMap: "Mapa climático interactivo", zoomIn: "Acercar", zoomOut: "Alejar", climateDataChoice: "Selección de datos climáticos", display: "Mostrar", rainyDays: "Días de lluvia", compositeScore: "Puntuación compuesta", intensity: "Intensidad", climateLayerIntensity: "Intensidad de la capa climática", learnMore: "Más información", methodSourcesScore: "Método, fuentes y puntuación meteorológica", aboutLabel: "Acerca de Better Weather Place", legend: "Leyenda", hoveredPointData: "Datos climáticos del punto señalado", updatingData: "Actualizando datos", hoverData: "Datos al pasar el cursor", exploreMap: "Explora el mapa", hoverHint: "Pasa el cursor sobre el mapa para comparar los indicadores meteorológicos de este lugar.", monthlyNormals: "Normales mensuales 1991–2020", readingData: "Leyendo datos…", unavailable: "N/D", monthChoice: "Elegir mes", previousMonth: "Mes anterior", nextMonth: "Mes siguiente", mapLoading: "Cargando el mapa…", resourceError: "No se ha podido cargar un recurso del mapa", loading: "Cargando", mapSourcesLabel: "Fuentes y atribuciones del mapa", closeSources: "Cerrar fuentes y atribuciones", mapAndData: "Mapa y datos", sourcesAndAttributions: "Fuentes y atribuciones", sourcesDescription: "Origen de los datos climáticos, geográficos y cartográficos.", climateData: "Datos climáticos", baseMap: "Mapa base", geographicData: "Datos geográficos", osmContributors: "© colaboradores de OpenStreetMap", terrain: "Relieve", terrainProvider: "Mapzen Terrain Tiles en AWS", closeAbout: "Cerrar la ventana Acerca de", aboutTitle: "Encuentra el mejor equilibrio meteorológico", aboutBeforeLink: "Better Weather Place es un", openSourceMap: "mapa de código abierto", aboutAfterLink: "que permite visualizar, mes a mes, las regiones más agradables para vivir según distintos criterios climáticos.", scoring: "Puntuación", scoringDescription: "La puntuación meteorológica mensual va de 0 a 100. Combina cuatro criterios mediante una media geométrica, por lo que un resultado muy malo no puede compensarse por completo con los demás.", scoreComposition: "Composición de la puntuación meteorológica", day: "Día", dayIdeal: "ideal entre 22 y 27 °C", night: "Noche", nightIdeal: "ideal entre 12 y 18 °C", sun: "Sol", sunIdeal: "ideal entre 6 y 9 h/día", rain: "Lluvia", rainIdeal: "se favorecen acumulados bajos", scoreDetail: "Las desviaciones se penalizan progresivamente en ambos sentidos, con una penalización adicional cuando coinciden mucho calor y mucho sol. Esta puntuación es una referencia de confort general, no una previsión ni un consejo médico.", dataAndMethod: "Datos y método", temperatureSourceDetail: "temperaturas y precipitación, aprox. 1 km.", sunshineSourceDetail: "duración de la insolación, unos 5 km y hasta 65° N.", normalsDetail: "Normales climáticas mensuales de 1991–2020; resolución de la puntuación: unos 5 km.", openGithub: "Abrir GitHub", language: "Idioma",
    },
  },
  de: {
    locale: "de-DE",
    metaDescription: "Entdecke die monatlichen Klimanormalwerte 1991–2020 für Europa und den Mittelmeerraum.",
    months: ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."],
    layers: {
      comfort: { label: "Wetterbewertung", shortLabel: "Bewertung", unit: sharedLayerValues.comfortUnit, source: "Kombinierte Bewertung aus CHELSA + SARAH-3", resolution: "ca. 5 km" },
      tavg: { label: "Durchschnittstemperatur", shortLabel: "Temperatur", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "ca. 1 km" },
      tmax: { label: "Tagestemperatur", shortLabel: "Tag", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "ca. 1 km" },
      tmin: { label: "Nachttemperatur", shortLabel: "Nacht", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "ca. 1 km" },
      precipitation: { label: "Monatlicher Niederschlag", shortLabel: "Gesamtregen", unit: "mm/Monat", source: "CHELSA-monthly V2.1", resolution: "ca. 1 km" },
      sunshine: { label: "Sonnenscheindauer", shortLabel: "Sonne", unit: "Std./Monat", source: "SARAH-3 (bis 65° N)", resolution: "ca. 5 km" },
    },
    ui: {
      climateMap: "Interaktive Klimakarte", zoomIn: "Vergrößern", zoomOut: "Verkleinern", climateDataChoice: "Klimadaten auswählen", display: "Anzeigen", rainyDays: "Regentage", compositeScore: "Kombinierte Bewertung", intensity: "Intensität", climateLayerIntensity: "Intensität der Klimaschicht", learnMore: "Mehr erfahren", methodSourcesScore: "Methode, Quellen und Wetterbewertung", aboutLabel: "Über Better Weather Place", legend: "Legende", hoveredPointData: "Klimadaten des ausgewählten Punkts", updatingData: "Daten werden aktualisiert", hoverData: "Daten beim Überfahren", exploreMap: "Karte erkunden", hoverHint: "Bewege den Mauszeiger über die Karte, um die Wetterindikatoren dieses Ortes zu vergleichen.", monthlyNormals: "Monatliche Normalwerte 1991–2020", readingData: "Daten werden gelesen…", unavailable: "k. A.", monthChoice: "Monat auswählen", previousMonth: "Vorheriger Monat", nextMonth: "Nächster Monat", mapLoading: "Karte wird geladen…", resourceError: "Eine Kartenressource konnte nicht geladen werden", loading: "Wird geladen", mapSourcesLabel: "Kartenquellen und Zuordnungen", closeSources: "Quellen und Zuordnungen schließen", mapAndData: "Karte und Daten", sourcesAndAttributions: "Quellen und Zuordnungen", sourcesDescription: "Herkunft der Klima-, Geografie- und Kartendaten.", climateData: "Klimadaten", baseMap: "Grundkarte", geographicData: "Geografische Daten", osmContributors: "© OpenStreetMap-Mitwirkende", terrain: "Relief", terrainProvider: "Mapzen Terrain Tiles auf AWS", closeAbout: "Infofenster schließen", aboutTitle: "Den besten Wetterkompromiss finden", aboutBeforeLink: "Better Weather Place ist eine", openSourceMap: "Open-Source-Karte", aboutAfterLink: "mit der sich Monat für Monat die Regionen mit den angenehmsten Lebensbedingungen anhand verschiedener Klimakriterien erkunden lassen.", scoring: "Bewertung", scoringDescription: "Die monatliche Wetterbewertung reicht von 0 bis 100. Sie kombiniert vier Kriterien mit einem geometrischen Mittel, sodass ein sehr schlechtes Ergebnis nicht vollständig durch die anderen ausgeglichen werden kann.", scoreComposition: "Zusammensetzung der Wetterbewertung", day: "Tag", dayIdeal: "ideal zwischen 22 und 27 °C", night: "Nacht", nightIdeal: "ideal zwischen 12 und 18 °C", sun: "Sonne", sunIdeal: "ideal zwischen 6 und 9 Std./Tag", rain: "Regen", rainIdeal: "geringe Mengen werden bevorzugt", scoreDetail: "Abweichungen werden auf beiden Seiten zunehmend bestraft; eine zusätzliche Strafe gilt, wenn große Hitze und starker Sonnenschein zusammenkommen. Diese Bewertung dient als allgemeine Komfortorientierung, nicht als Vorhersage oder medizinischer Rat.", dataAndMethod: "Daten und Methode", temperatureSourceDetail: "Temperaturen und Niederschlag, ca. 1 km.", sunshineSourceDetail: "Sonnenscheindauer, ca. 5 km und bis 65° N.", normalsDetail: "Monatliche Klimanormalwerte 1991–2020; Auflösung der Bewertung: ca. 5 km.", openGithub: "GitHub öffnen", language: "Sprache",
    },
  },
  it: {
    locale: "it-IT",
    metaDescription: "Esplora le normali climatiche mensili 1991–2020 in Europa e nel Mediterraneo.",
    months: ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"],
    layers: {
      comfort: { label: "Punteggio meteo", shortLabel: "Punteggio", unit: sharedLayerValues.comfortUnit, source: "Punteggio composito CHELSA + SARAH-3", resolution: "circa 5 km" },
      tavg: { label: "Temperatura media", shortLabel: "Temperatura", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "circa 1 km" },
      tmax: { label: "Temperatura diurna", shortLabel: "Giorno", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "circa 1 km" },
      tmin: { label: "Temperatura notturna", shortLabel: "Notte", unit: sharedLayerValues.temperatureUnit, source: "CHELSA-monthly V2.1", resolution: "circa 1 km" },
      precipitation: { label: "Precipitazioni mensili", shortLabel: "Pioggia totale", unit: "mm/mese", source: "CHELSA-monthly V2.1", resolution: "circa 1 km" },
      sunshine: { label: "Durata del soleggiamento", shortLabel: "Sole", unit: "h/mese", source: "SARAH-3 (fino a 65° N)", resolution: "circa 5 km" },
    },
    ui: {
      climateMap: "Mappa climatica interattiva", zoomIn: "Ingrandisci", zoomOut: "Riduci", climateDataChoice: "Scelta dei dati climatici", display: "Mostra", rainyDays: "Giorni di pioggia", compositeScore: "Punteggio composito", intensity: "Intensità", climateLayerIntensity: "Intensità del livello climatico", learnMore: "Scopri di più", methodSourcesScore: "Metodo, fonti e punteggio meteo", aboutLabel: "Informazioni su Better Weather Place", legend: "Legenda", hoveredPointData: "Dati climatici del punto selezionato", updatingData: "Aggiornamento dei dati", hoverData: "Dati al passaggio", exploreMap: "Esplora la mappa", hoverHint: "Passa sulla mappa per confrontare gli indicatori meteo di questo luogo.", monthlyNormals: "Normali mensili 1991–2020", readingData: "Lettura dei dati…", unavailable: "N/D", monthChoice: "Scegli il mese", previousMonth: "Mese precedente", nextMonth: "Mese successivo", mapLoading: "Caricamento della mappa…", resourceError: "Non è stato possibile caricare una risorsa della mappa", loading: "Caricamento", mapSourcesLabel: "Fonti e attribuzioni della mappa", closeSources: "Chiudi fonti e attribuzioni", mapAndData: "Mappa e dati", sourcesAndAttributions: "Fonti e attribuzioni", sourcesDescription: "Origine dei dati climatici, geografici e cartografici.", climateData: "Dati climatici", baseMap: "Mappa di base", geographicData: "Dati geografici", osmContributors: "© collaboratori di OpenStreetMap", terrain: "Rilievo", terrainProvider: "Mapzen Terrain Tiles su AWS", closeAbout: "Chiudi la finestra Informazioni", aboutTitle: "Trova il miglior compromesso meteorologico", aboutBeforeLink: "Better Weather Place è una", openSourceMap: "mappa open source", aboutAfterLink: "che consente di visualizzare, mese per mese, le regioni più piacevoli in cui vivere secondo diversi criteri climatici.", scoring: "Punteggio", scoringDescription: "Il punteggio meteo mensile va da 0 a 100. Combina quattro criteri con una media geometrica, quindi un risultato molto scarso non può essere compensato completamente dagli altri.", scoreComposition: "Composizione del punteggio meteo", day: "Giorno", dayIdeal: "ideale tra 22 e 27 °C", night: "Notte", nightIdeal: "ideale tra 12 e 18 °C", sun: "Sole", sunIdeal: "ideale tra 6 e 9 h/giorno", rain: "Pioggia", rainIdeal: "si favoriscono quantità ridotte", scoreDetail: "Gli scostamenti vengono penalizzati progressivamente in entrambe le direzioni, con una penalità aggiuntiva quando calore intenso e forte soleggiamento coincidono. Questo punteggio è un indicatore di comfort generale, non una previsione né un consiglio medico.", dataAndMethod: "Dati e metodo", temperatureSourceDetail: "temperature e precipitazioni, circa 1 km.", sunshineSourceDetail: "durata del soleggiamento, circa 5 km e fino a 65° N.", normalsDetail: "Normali climatiche mensili 1991–2020; risoluzione del punteggio: circa 5 km.", openGithub: "Apri GitHub", language: "Lingua",
    },
  },
};

export function detectLanguage(): Language {
  const preferredLanguages = typeof navigator === "undefined"
    ? []
    : navigator.languages.length
      ? navigator.languages
      : [navigator.language];
  for (const preferredLanguage of preferredLanguages) {
    const baseLanguage = preferredLanguage.toLowerCase().split("-")[0];
    if (supportedLanguages.some(language => language === baseLanguage)) {
      return baseLanguage as Language;
    }
  }
  return "en";
}
