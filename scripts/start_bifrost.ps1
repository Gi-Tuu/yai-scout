# Start Bifrost locally for the Scout demo.
# Requires Docker Desktop. Bifrost UI: http://localhost:8080
docker run --rm -p 8080:8080 -v "${PWD}\data\bifrost:/app/data" maximhq/bifrost
