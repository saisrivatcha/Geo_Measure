# GeoMeasure API

GeoMeasure is a backend service built with **FastAPI** that accepts geospatial files (Shapefile in `.zip`, or `.kml`), processes the features within them, and returns accurate area and length measurements.

## 🚀 Setup & Running Locally

The easiest way to run the application is using Docker Compose.

### Prerequisites
- Docker and Docker Compose installed on your machine.

### Instructions

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd geomeasure
   ```

2. **Start the application:**
   Using the provided Makefile:
   ```bash
   make up
   ```
   *This will automatically copy `.env.example` to `.env`, build the containers, run database migrations, and start the services.*

3. **Access the services:**
   - **Frontend App:** http://localhost:5173
   - **API Documentation (Swagger):** http://localhost:8000/api/docs
   - **Health Check:** http://localhost:8000/api/health/ready

To stop the application, run:
```bash
make down
```

## 📖 API Documentation

Detailed interactive API documentation is available at `http://localhost:8000/api/docs` when the server is running. 

### Core Endpoints

#### 1. Upload a File
`POST /api/files/`
Uploads and processes a `.zip` (containing a Shapefile) or `.kml` file.

**Example Request (cURL):**
```bash
curl -X POST "http://localhost:8000/api/files/" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@my_shapefile.zip"
```

#### 2. Get File Information
`GET /api/files/{id}/`
Returns metadata and processing status about the uploaded file.

**Example Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "filename": "survey.kml",
  "feature_count": 120,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

#### 3. Get Measurements
`GET /api/files/{id}/measurements/`
Returns the measurements (area/length), geometry type, and attributes for the features in the file.

**Example Response:**
```json
{
  "items": [
    {
      "feature_index": 0,
      "properties": {"name": "Park"},
      "geometry_type": "Polygon",
      "measurement": {
        "status": "COMPLETED",
        "measurement_type": "AREA",
        "value": 4520.5,
        "unit": "SQUARE_METERS"
      }
    }
  ],
  "page": 1,
  "page_size": 50,
  "total": 1
}
```

## 🏗️ Architecture

### Application Structure
The backend is built using a modern **FastAPI** architecture layered into routes, services, repositories, and a geospatial processing core. It is backed by a **PostgreSQL** database (using SQLAlchemy/Alembic) to store file metadata and measurements.

### File-Processing Flow
1. The user uploads a `.zip` or `.kml`. 
2. The file is validated and safely extracted (preventing zip-bombs and path traversal).
3. The file is read using `pyogrio` and `geopandas`, extracting geometries, properties, and the source CRS.
4. Data is handed off to the measurement engine.

### Measurement Calculation Flow
Measurements are heavily vectorized using Shapely 2 and NumPy to maximize performance.
1. Geometries are classified (Polygon, LineString, Point, etc.).
2. Valid geometries are identified; invalid ones are repaired if possible.
3. Unsupported geometries (like Points or GeometryCollections) are flagged gracefully as `NOT_REQUIRED` or `NOT_SUPPORTED`.
4. Supported features are transformed to a projected CRS and their Area or Length is calculated.

### CRS Handling
The application never calculates distance or area directly using geographic coordinates (latitude/longitude degrees).
Instead, it dynamically selects the most appropriate **Metric Projected CRS** to minimize distortion based on the dataset's geographic bounds:
- It checks if the source CRS is already a projected metric system.
- If not, it falls back to the appropriate WGS 84 UTM zone.
- For datasets spanning multiple zones, it utilizes a dataset-centered Transverse Mercator or Lambert Azimuthal Equal-Area projection.

## 💡 Design Decisions

- **Vectorized Geospatial Processing:** Instead of looping through features in standard Python, the application relies on `GeoPandas` and `Shapely` C-extensions to process features in arrays. This vastly improves performance on large datasets.
- **Strict File Validation:** Uploaded archives are inspected *before* extraction. This prevents malicious uploads, duplicate names, and ensures only valid `.shp`, `.shx`, and `.dbf` files are processed.
- **Graceful Error Handling:** If a file contains a mix of valid Polygons and unsupported GeometryCollections, the application processes the valid shapes and simply flags the unsupported ones in the API response, rather than rejecting the entire file.

## 🚀 Learning and Future Scope

### Learnings
- Experience working deeply with Geospatial data formats (Shapefiles, KML).
- Advanced understanding of Coordinate Reference Systems (CRS) and the importance of projecting to metric coordinate systems for accurate area/length measurements using PyProj and GeoPandas.
- Implementing robust file processing, validation, and safe archive extraction in Python.

### Future Scope
- **Support for more formats:** Expand compatibility to include GeoJSON, GeoPackage (GPKG), or raster data.
- **Asynchronous Processing:** Shift heavy geospatial file processing to a background task queue (like Celery or RQ) for extremely large datasets to avoid blocking API HTTP responses.
- **Map Visualization UI:** Enhance the frontend to include an interactive map (e.g., using Mapbox or Leaflet) where users can visualize their uploaded features alongside the calculated measurements.
