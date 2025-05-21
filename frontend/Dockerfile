FROM node:18-alpine

WORKDIR /usr/src/app
COPY package*.json ./
RUN npm install

# for hot-reload we mount the source in later
COPY . .
EXPOSE 3000

# start the CRA dev server
CMD ["npm", "start"]
