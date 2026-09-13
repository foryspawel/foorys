FROM node:22-alpine
WORKDIR /app
COPY package.json server.js ./
COPY web ./web
RUN addgroup -S relay && adduser -S relay -G relay
RUN mkdir -p /data && chown -R relay:relay /data
USER relay
EXPOSE 8080
CMD ["node", "server.js"]
