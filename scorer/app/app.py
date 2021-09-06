from os import environ
import library.scoring
import json
import os
from twisted.web import server, resource
from twisted.internet import reactor, endpoints
from twisted.web.server import Site
from twisted.internet.threads import deferToThread
from twisted.web.server import NOT_DONE_YET


class Scorer(resource.Resource):
    def _delayedRender(self, request):
        result = request[1]
        request = request[0]
        request.setHeader(b"content-type", b"text/json")
        request.write(result)
        request.finish()

    def _responseFailed(self, err, call):
        call.cancel()

    def render_POST(self, request):
        d = deferToThread(webserver_handler, request)
        request.notifyFinish().addErrback(self._responseFailed, d)
        d.addCallback(self._delayedRender)
        return NOT_DONE_YET
        
        
       

def webserver_handler(request):
    input = json.loads(request.content.read().decode("utf-8"))
    content = json.dumps(lambda_handler(input, None))
    return (request, content.encode("utf-8"))


def lambda_handler(event, context):
    try:
        url = event["url"]
        signal = event["signal"]
        text = event["text"]
        score, new_signal = library.scoring.get_score(signal, url, text) #In case, for some reason, the name of the signal gets updated

        #print(url + "_" + new_signal + "_score: " + str(score))
    except Exception as e:
        print("\n" + "\n" + e + "\n" + "\n")
        return {"url": "None", "signal": "None", "score": "None", "error": str(e)}
    return {"url": url, "signal": signal, "score": score}

root = resource.Resource()
root.putChild(b"scorer", Scorer())
factory = Site(root)
endpoint = endpoints.TCP4ServerEndpoint(reactor, 8025)
endpoint.listen(factory)
if "SCORER_THREADPOOL_SIZE" in os.environ and os.environ["SCORER_THREADPOOL_SIZE"] != "":
    reactor.getThreadPool().adjustPoolsize(None, int(os.environ["SCORER_THREADPOOL_SIZE"]))
reactor.run()
