FROM node:22-alpine AS base
WORKDIR /app
RUN corepack enable && corepack prepare yarn@1.22.22 --activate

FROM base AS dependencies
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --non-interactive

FROM dependencies AS development
COPY . .
ARG VITE_BACKEND_URL=http://localhost:7007
ARG REACT_APP_BACKEND_URL=http://localhost:7007
ENV DEV_PORT=5173 \
    VITE_BACKEND_URL=${VITE_BACKEND_URL} \
    REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL}
EXPOSE 5173
CMD ["yarn", "dev", "--host", "0.0.0.0"]

FROM dependencies AS build
COPY . .
ARG VITE_BACKEND_URL=http://localhost:7007
ARG REACT_APP_BACKEND_URL=http://localhost:7007
ARG VITE_API_SAME_ORIGIN=false
ENV DEV_PORT=5173 \
    VITE_BACKEND_URL=${VITE_BACKEND_URL} \
    REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL} \
    VITE_API_SAME_ORIGIN=${VITE_API_SAME_ORIGIN}
RUN yarn build

FROM nginx:1.27-alpine AS production
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 5173