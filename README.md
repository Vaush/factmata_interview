# Reddit scraper
This program's aim is to scrape the topmost n links in an arbitrary subreddit's view, with an optional time filter, and run concurrently a series of analyses on the text of the linked page, to then store the results in a MongoDB database.
At this stage, the MongoDB instance and the reddit access data are hardcoded to simplify the structure, but they can easily be pulled out of the code.
The program itself is divided in two main components: the links_retriever, and the scorer. The scorer is a multithreaded application that receives analysis requests and runs them asynchronously, while the links retriever receives a scraping request, scrapes the links, parses their text, and calls the scorer as needed, employing multiple threads in both the parsing and the scorer calling steps.
The two applications depend on some environment variables which work across all the available deployment methods:
- RETRIEVER_THREADPOOL_SIZE -> Maximum number of threads employed by links_retriever
- SCORER_THREADPOOL_SIZE -> Maximum number of threads employed by scorer
- MONGODB_CONNECTION_URL -> Connection URL for the MongoDB instance where to store results and metrics. The current one is mongodb://factmata:factmata@aspronedario.com/factmata_interview.
- IS_LAMBDA_AWS -> Either TRUE or FALSE, self-explanatory
In addition, the following variable has to be used when deploying on AWS Lambda
- AWS_SCORER_FUNCTION_NAME -> The name of the AWS Lambda function for scorer
## Parameters
### links_retriever
Independently from the deployment method, links_retriever accepts 4 parameters:
- view -> The view to be used for the requested subreddit. Can be one of hot, top, new, controversial, or rising.
- n -> The number of links to obtain from reddit. Any number above 1000 is useless as reddit does not keep record after 1000.
- subreddit_name -> The name of the subreddit to get the links from. Multiple subreddits can be used by joining their names with the '+' symbol.
- time_filter -> Only used for view="top" or view="controversial", represents the timeframe during which the posts should be considered for the ranking, such as last day's post, last week's, etc. Can be one of: all, day, hour, month, week, year.
### scorer
Independently from the deployment method, scorer accepts 3 parameters:
- url -> The URL from which the text was parsed
- text -> The parsed text
- signal -> The name of the analysis to be carried out
## Deployment methods
### Standalone
The two programs can be run as is, by just running the two scripts. For this to work, the hosts file on the system will have to assign the domain name loadbalancer to 127.0.0.1. Running the scorer and then the links_retriever from the command line with the arguments in the order in which they were presented above, a request will be performed to links retriever and then, subsequently, to scorer, both of which will be carried out in a multithreaded way.
This method does not allow for true parallelism, as all the calculations are still done on a single process/core.
### Docker compose
Both programs have a Dockerfile in their folder, and the corresponding images can be created and run by using docker compose in the root directory.
In particular, in the docker compose file there is also a load balancing service provided by nginx, which can allow true parallelism by spinning up multiple copies of scorer and distributing the load among the copies, if such a thing was needed due to the CPU bound nature of the requested analyses.
To do so, the command would be:
  docker-compose up --scale scorer=M
where M is the number of needed copies of scorer.
Please do remember that in order to customise the number of threads, the environment variables presented above can still be used.
As a default,
  docker-compose up --scale scorer=30
should provide enough performance.
After this, a request can be sent to links_retriever by sending a POST request to localhost:8080 with the required parameters (see above) passed as JSON data.
### AWS Lambda
Both applications are ready to be deployed on AWS Lambda. For links_retriever, the entire docker image can simply be uploaded to the AWS Elastic Container Registry and then imported into AWS Lambda, while for scorer a second Dockerfile, very similar to the links_retriever one, would be needed. Both applications' code already contains the lambda handler function and the correct folder structure, furthermore by setting the IS_AWS_LAMBDA environment variable links_retriever will switch automatically to invoking scorer as an AWS Lambda function. Please do keep in mind that links_retriever will call the scorer function once per signal, that is #URLS times #SIGNALS, so factor this is during deployment.
The only extra step needed to run the system is to assign the invoking permissions on AWS to the links_retriever function, and to set up a trigger of some kind to run links_retriever, such as AWS SNS or the CLI.
## Metrics and data storage
The program stores all its data in a MongoDB database. The one used as demonstration can be accessed from anywhere by installing the mongodb client and using the following command:
  mongo -u factmata -p factmata mongodb://aspronedario.com/factmata_interview
The database is factmata_interview, and the collections are scores and monitoring. Scores contains the results of all the analyses on all the texts, while the other contains the following monitoring metrics for each links_retriever request:
- The values of the 4 parameters
- The deployment method (platform)
- The time of the request (request_time)
- Possible error type (error, "None" if no error)
- The error message of the possible error (error_message, does not exists if no error)
- The time it took to fulfill the request (ellapsed_milliseconds)
- The number of links that were parseable (readable_links)
- The number of analyses run (calculated_scores)

This data allows us to monitor the 4 most important metrics for a data pipeline:
- Latency -> Through ellapsed_milliseconds
- Traffic -> By counting the number of documents in the collection
- Errors -> By counting the number of documents in the collections with error different from "None"
- Saturation -> This particular metric only has meaning in a larger deployment, but for example it could be easily checked through the AWS console in case of a deployment on AWS Lambda

## Design choices
I have decided to split the program in two parts as there were clearly two distinct roles, one to retrieve the data, and one to analyse it. As such, it made sense to create two different applications for these roles and make them communicate via network, so as to allow them to be as close or as far as needed. 
Both programs have been made multithreaded: links_retriever spends a lot of time waiting on results from scorer, while scorer spends a lot of time waiting for results from the analyses, and as such both can benefit from using multiple threads.
The reason why multiprocessing was not used is to allow for better scalability: although in theory multiprocessing would give better performance, in this and most other cases multithreading performs just as well, while avoiding all the issues with having too many processes or files open. Still, since multiprocessing could be useful when doing CPU bound analyses, it was incorporated as an option in the docker compose setup. Since there could be many more requests than copies of scorer active, a simple Twisted webserver was set up in order to manage the requests easily, and deal with them when possible.
Although originally the request was to only calculate the 30 scores concurrently, I preferred making it as parallelised as possible, since the speed up does not impact any other aspect of the system. The original request can still be achieved by setting a RETRIEVER_THREADPOOL_SIZE of 30 (or as much as the number of signals).
The program also allows to choose different subreddits, views, etc. as it was more general this way. As a note, the system discards any reddit posts which are not links to parseable articles.
As a final remark, I also chose to make scorer a one-request-per-signal system, as it decouples scorer from knowing anything about the structure of the overarching system, while also allowing for better fine-tuning and easier integration with AWS Lambda if needed.
