docker build --platform linux/amd64 -t 83.166.249.64:5000/10176/index-service:latest ./index
docker build --platform linux/amd64 -t 83.166.249.64:5000/10176/search-service:latest ./search

docker push 83.166.249.64:5000/10176/index-service:latest
docker push 83.166.249.64:5000/10176/search-service:latest