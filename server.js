// server.js - Backend API to serve ArcGIS service URLs securely
const express = require('express');
const cors = require('cors');
const rateLimit = require('express-rate-limit');
const helmet = require('helmet');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3001;

// Security middleware
app.use(helmet());
app.use(cors({
  origin: process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000'],
  credentials: true
}));

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  message: 'Too many requests from this IP, please try again later.'
});
app.use('/api/', limiter);

app.use(express.json());

// Store service URLs securely (should be in environment variables or secure config)
const SERVICE_URLS = {
  usa_map: process.env.USA_MAP_SERVER || "https://sampleserver6.arcgisonline.com/arcgis/rest/services/USA/MapServer",
  world_cities: process.env.WORLD_CITIES_SERVER || "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/World_Cities/FeatureServer",
  census: process.env.CENSUS_SERVER || "https://sampleserver6.arcgisonline.com/arcgis/rest/services/Census/MapServer",
  water_network: process.env.WATER_NETWORK_SERVER || "https://sampleserver6.arcgisonline.com/arcgis/rest/services/Water_Network/FeatureServer",
  osm_pois: process.env.OSM_POIS_SERVER || "https://services-ap1.arcgis.com/iA7fZQOnjY9D67Zx/arcgis/rest/services/OSM_AS_POIs/FeatureServer",
  osm_buildings: process.env.OSM_BUILDINGS_SERVER || "https://services-ap1.arcgis.com/iA7fZQOnjY9D67Zx/ArcGIS/rest/services/OSM_AS_Buildings/FeatureServer/",
  osm_amenities: process.env.OSM_AMENITIES_SERVER || "https://services-ap1.arcgis.com/iA7fZQOnjY9D67Zx/ArcGIS/rest/services/OSM_AS_Amenities/FeatureServer/",
  osm_shops: process.env.OSM_SHOPS_SERVER || "https://services-ap1.arcgis.com/iA7fZQOnjY9D67Zx/ArcGIS/rest/services/OSM_AS_Shops/FeatureServer",
  osm_leisure: process.env.OSM_LEISURE_SERVER || "https://services-ap1.arcgis.com/iA7fZQOnjY9D67Zx/ArcGIS/rest/services/OSM_AS_Leisure/FeatureServer",
  osm_highways: process.env.OSM_HIGHWAYS_SERVER || "https://services-ap1.arcgis.com/iA7fZQOnjY9D67Zx/ArcGIS/rest/services/OSM_AS_Highways/FeatureServer"
};

// Simple authentication middleware (you should implement proper auth)
const authenticate = (req, res, next) => {
  const apiKey = req.headers['x-api-key'];
  const validApiKey = process.env.API_KEY;
  
  if (!validApiKey) {
    return next(); // Skip auth if no API key is set (for development)
  }
  
  if (!apiKey || apiKey !== validApiKey) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  
  next();
};

// API endpoint to get service URLs
app.get('/api/services', authenticate, (req, res) => {
  try {
    // Only return the URLs, not the keys
    const serviceUrls = Object.values(SERVICE_URLS);
    res.json({ services: serviceUrls });
  } catch (error) {
    console.error('Error fetching services:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// API endpoint to get specific service metadata
app.get('/api/service/:serviceId', authenticate, async (req, res) => {
  try {
    const { serviceId } = req.params;
    const serviceUrl = SERVICE_URLS[serviceId];
    
    if (!serviceUrl) {
      return res.status(404).json({ error: 'Service not found' });
    }
    
    // Proxy the request to the ArcGIS service
    const response = await fetch(`${serviceUrl}?f=json`);
    const data = await response.json();
    
    if (data.error) {
      return res.status(400).json({ error: data.error.message });
    }
    
    res.json(data);
  } catch (error) {
    console.error('Error fetching service metadata:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({ status: 'OK', timestamp: new Date().toISOString() });
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

module.exports = app;