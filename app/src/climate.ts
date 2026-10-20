export type ColorStop = readonly [number, string];

export type ClimateLayer = {
	id: string;
	label: string;
	shortLabel: string;
	unit: string;
	source: string;
	resolution: string;
	maxZoom: number;
	stops: readonly ColorStop[];
};

const temperatureStops = [
	[-20, '#4575b4'],
	[-10, '#74add1'],
	[-5, '#abd9e9'],
	[0, '#e0f3f8'],
	[5, '#ffffbf'],
	[10, '#fee090'],
	[15, '#fdae61'],
	[20, '#f46d43'],
	[25, '#d73027'],
	[35, '#a50026'],
	[40, '#67001f'],
] as const;

export const climateLayers: readonly ClimateLayer[] = [
	{
		id: 'tavg',
		label: 'Température moyenne',
		shortLabel: 'Température',
		unit: '°C',
		source: 'CHELSA-monthly V2.1',
		resolution: 'environ 1 km',
		maxZoom: 7,
		stops: temperatureStops,
	},
	{
		id: 'tmax',
		label: 'Moyenne des maximales',
		shortLabel: 'Maximales',
		unit: '°C',
		source: 'CHELSA-monthly V2.1',
		resolution: 'environ 1 km',
		maxZoom: 7,
		stops: temperatureStops,
	},
	{
		id: 'tmin',
		label: 'Moyenne des minimales',
		shortLabel: 'Minimales',
		unit: '°C',
		source: 'CHELSA-monthly V2.1',
		resolution: 'environ 1 km',
		maxZoom: 7,
		stops: temperatureStops,
	},
	{
		id: 'precipitation',
		label: 'Précipitations mensuelles',
		shortLabel: 'Pluie totale',
		unit: 'mm/mois',
		source: 'CHELSA-monthly V2.1',
		resolution: 'environ 1 km',
		maxZoom: 7,
		stops: [
			[0, '#fff7dc'],
			[5, '#fee8a6'],
			[10, '#fdd477'],
			[20, '#f6b84c'],
			[40, '#e88f3c'],
			[60, '#d26145'],
			[100, '#ad3d5d'],
			[150, '#7b2f70'],
			[250, '#47206f'],
			[400, '#21104f'],
		],
	},
	{
		id: 'sunshine',
		label: 'Durée d’ensoleillement',
		shortLabel: 'Soleil',
		unit: 'h/mois',
		source: 'SARAH-3 (jusqu’à 65° N)',
		resolution: 'environ 5 km',
		maxZoom: 5,
		stops: [
			[0, '#2d1e3e'],
			[20, '#44345f'],
			[40, '#5d4d7a'],
			[80, '#786b91'],
			[120, '#958baa'],
			[160, '#b3acc0'],
			[200, '#d2cfbe'],
			[240, '#eee9a9'],
			[280, '#f6d66f'],
			[320, '#f7b942'],
			[360, '#f28e2b'],
			[400, '#d95f0e'],
		],
	},
] as const;

export const months = [
	'janv.',
	'févr.',
	'mars',
	'avr.',
	'mai',
	'juin',
	'juil.',
	'août',
	'sept.',
	'oct.',
	'nov.',
	'déc.',
] as const;

const DATA_VERSION = '2026-10-20.2';

export function climateArchiveUrl(layerId: string, month: number): string {
	const relative = `/data/1991-2020/${layerId}/${String(month).padStart(2, '0')}.pmtiles`;
	const url = new URL(relative, window.location.href);
	url.searchParams.set('v', DATA_VERSION);
	return `pmtiles://${url.href}`;
}
