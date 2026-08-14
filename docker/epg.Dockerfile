# Pinned iptv-org/epg build. Update EPG_GIT_REF deliberately when upgrading.
ARG EPG_GIT_REF=0e03581
FROM node:20-bookworm-slim
ARG EPG_GIT_REF
WORKDIR /epg
RUN apt-get update -qq \
 && apt-get install -y -qq --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && git clone --filter=blob:none --no-checkout https://github.com/iptv-org/epg.git /tmp/epg-src \
 && git -C /tmp/epg-src fetch --depth 1 origin ${EPG_GIT_REF} \
 && git -C /tmp/epg-src checkout --detach ${EPG_GIT_REF} \
 && cp -a /tmp/epg-src/. /epg/ \
 && npm ci --omit=dev \
 && rm -rf /tmp/epg-src
COPY docker/epg-server.mjs /usr/local/bin/epg-server.mjs
COPY scripts/epg-sidecar-entrypoint.sh /usr/local/bin/epg-entrypoint.sh
RUN chmod +x /usr/local/bin/epg-entrypoint.sh
ENV NODE_ENV=production
EXPOSE 3000
ENTRYPOINT ["/usr/local/bin/epg-entrypoint.sh"]
