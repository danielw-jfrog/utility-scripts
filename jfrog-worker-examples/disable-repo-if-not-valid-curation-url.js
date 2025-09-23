export default async (
  context: PlatformContext,
  data: ScheduledEventRequest
): Promise<ScheduledEventResponse> => {
  try {
    
    // Current list of supported curation URLs by package type
    //    per: https://jfrog.com/help/r/jfrog-security-user-guide/products/curation/supported-technologies
    var curation_urls = {
        npm: ["https://registry.npmjs.org"],
        docker: ["https://registry-1.docker.io"],
        maven: ["https://repo.maven.apache.org/maven2", "https://repo1.maven.org/maven2", "https://maven.google.com"],
        pypi: ["https://files.pythonhosted.org"],
        go: ["https://proxy.golang.org"],
        nuget: ["https://www.nuget.org"],
        conan: ["https://center.conan.io"],
        huggingfaceml: ["https://huggingface.co"],
        ruby: ["https://rubygems.org"],
        gradle: ["https://repo1.maven.org/maven2", "https://repo.maven.apache.org/maven2", "https://maven.google.com"],
        cargo: ["https://index.crates.io"],
        conda: ["https://repo.anaconda.com/pkgs"]
    };
    
    const res = await context.clients.platformHttp.get(
      "/artifactory/api/repositories/configurations?repoType=remote"
    );

    // You should reach this part if the HTTP request status is successful (HTTP Status 399 or lower)
    if (res.status === 200) {
      //console.log(`Artifactory GET repo config success: ${JSON.stringify(res)}`);
      
      // for each repo config in result (remote repo configs)
      for (var repo_num in res.data["REMOTE"]) {
        //console.log(`one repo: ${JSON.stringify(res.data["REMOTE"][repo_num])}`)
        // if not offline
        if (res.data["REMOTE"][repo_num]["offline"] == false) {
          //console.log(`  - repo not offline`)
          // if package type is in curation_urls
          if (curation_urls.hasOwnProperty(res.data["REMOTE"][repo_num]["packageType"])) {
            // if url not in curation_urls[package type]
            if (curation_urls[res.data["REMOTE"][repo_num]["packageType"]].includes(res.data["REMOTE"][repo_num]["url"].replace(/\/$/, ""))) {
              //console.log(`  - curation_url valid`)
            } else {
              // set repo offline
              console.log(`  --- curation url invalid, setting offline: repo_key: ${res.data["REMOTE"][repo_num]["key"]}, packageType: ${res.data["REMOTE"][repo_num]["packageType"]}, url: ${res.data["REMOTE"][repo_num]["url"]}`)
              const res2 = await context.clients.platformHttp.post(`/artifactory/api/repositories/${res.data["REMOTE"][repo_num]["key"]}`, {
                  offline: true
              });
              // --- Add error handling here to check the offline setting request ---
            }
          } else {
            console.warn(`packageType not in curation_urls: ${res.data["REMOTE"][repo_num]["packageType"]}`)
          }
        }
      }
      
      
    } else {
      console.warn(
        `GET Request returned status other than 200. Status code : ${res.status}`
      );
    }
  } catch (error) {
    // The platformHttp client throws PlatformHttpClientError if the HTTP request status is 400 or higher
    console.error(
      `Request failed with status code ${
        error.status || "<none>"
      } caused by : ${error.message}`
    );
  }

  return {
    message: "Overwritten by worker-service if an error occurs.",
  };
};