FROM node:18-alpine as build

WORKDIR /app

# 의존성 파일 복사 및 설치
COPY package.json package-lock.json* ./
RUN npm ci

# 소스 코드 복사
COPY . .

# 빌드
RUN npm run build

# 프로덕션 환경
FROM nginx:alpine

# Nginx 설정 복사 (필요한 경우)
# COPY nginx.conf /etc/nginx/conf.d/default.conf

# 빌드 결과물 복사
COPY --from=build /app/dist /usr/share/nginx/html

# 환경 변수를 런타임에 주입하기 위한 스크립트 (선택 사항)
# COPY ./env.sh /docker-entrypoint.d/40-env.sh
# RUN chmod +x /docker-entrypoint.d/40-env.sh

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"] 