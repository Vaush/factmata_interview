from newspaper.article import ArticleException
import praw
from newspaper import Article
from . import signals

def get_signals_list():
    return signals.get_signals()

def get_urls(view, time_filter="all", n=100, subreddit_name="news"):
    reddit = praw.Reddit(client_id='YFvC2AocoGz0fN73P91SVQ', client_secret='LidjzU-eULwMD-sTM1WuyKdY5ZJLbg', user_agent='Factmata_0.0.1', username='FactmataInterview', password='InterviewFactmata')
    subreddit = reddit.subreddit(subreddit_name)
    f = getattr(subreddit, view, None)
    if f:
        return [x.url for x in f(time_filter = time_filter, limit=n)]
    else:
        return []


def get_text(url):
    article = Article(url)
    res = None
    try:
        article.download()
        article.parse()
        return article.text
    except ArticleException as e:
        return None

def get_score(signal: str, url: str, text: str, scores_dict: dict = None):
    new_signal, s = signals.score(signal, text)
    if scores_dict:
        scores_dict[url][new_signal] = s
    return s, new_signal


def main():
    l = get_urls("top", n = 100)
    texts = {url:get_text(url) for url in l}
    scores = {url:{} for url in l}
    for url,text in texts.items():
        for signal in signals.get_signals():
            get_score(signal, url, text, scores)

    print(scores)


if __name__ == "__main__":
    main()
