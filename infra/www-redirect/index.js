// Permanent redirect from www.walldye.com to the apex, keeping path and query.
export default {
  fetch(request) {
    const url = new URL(request.url);
    url.protocol = 'https:';
    url.hostname = 'walldye.com';
    url.port = '';
    return Response.redirect(url.toString(), 301);
  },
};
