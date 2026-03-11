FROM node:20-alpine AS build

WORKDIR /app

RUN echo ">>> [1/4] Installing dependencies..."
COPY package.json package-lock.json* ./
RUN npm install --legacy-peer-deps 2>&1 \
    && npm install ajv@8 --legacy-peer-deps 2>&1 \
    && echo ">>> Dependencies installed successfully"

RUN echo ">>> [2/4] Copying source files..."
COPY . .

ARG REACT_APP_BACKEND_URL=/api
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

RUN echo ">>> [3/4] Building frontend (this may take a few minutes)..."
RUN npm run build 2>&1 && echo ">>> Build completed successfully"

RUN echo ">>> [4/4] Preparing production image..."
FROM nginx:alpine

COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
