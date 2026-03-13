export default async (context: PlatformContext, data: BeforeDownloadRequestRequest): Promise<BeforeDownloadRequestResponse> => {

    let status: ActionStatus = ActionStatus.PROCEED;
    let message: string = "Proceed";

    try {

        if(data.metadata.name == "manifest.json" || data.metadata.name == "list.manifest.json") {
            console.log("Found a docker manifest or list manifest");

            // Get the labels from the graphql
            let dpackage: string = data.metadata.repoPath.path.split("/", 2).join("/");
            console.log(`Found Package: ${dpackage}`);
            // FIXME: Need to remove the 'library/' if the package starts with that.

            let query: string = `{ "query" : "{ publicPackage { getPackage(name: \\"${dpackage}\\" type: \\"docker\\") { name, type, customCatalogLabelsConnection(first:4) { edges { node { name } } } } } }"}`;
            console.log(`JSON: '${query}'`);
            const res = await context.clients.platformHttp.post('/catalog/api/v1/custom/graphql', query, {'Content-Type': 'application/json'});

            console.log(`res.status: ${res.status}`);
            console.log(`res.data: ${JSON.stringify(res.data)}`);
            console.log(`label count: ${res.data.data.publicPackage.getPackage.customCatalogLabelsConnection.edges.length}`);

            if(res.data.data.publicPackage.getPackage.customCatalogLabelsConnection.edges.length == 0) {
                // Apply the 'NEW_PACKAGE' label
                console.log("No labels found.  Applying.");

                let query2: string = `{ "query" : "mutation { customCatalogLabel { assignCustomCatalogLabelsToPublicPackage( publicPackageLabels: { publicPackage: { name: \\"${dpackage}\\", type:\\"docker\\"}, labelNames:[\\"NEW_PACKAGE\\"] } ) } }"}`;
                console.log(`JSON: '${query2}'`);
                const res2 = await context.clients.platformHttp.post('/catalog/api/v1/custom/graphql', query2, {'Content-Type': 'application/json'});
                console.log(`res2.status: ${res2.status}`);

                // Download the manifest file into the seconday repo
                //let new_repo: string = "20260313-secondary-remote";
                //let file_path: string = data.metadata.repoPath.path;
                //const res3 = await context.clients.platformHttp.get(`/artifactory/api/download/${new_repo}/${file_path}?content=none`);
                //console.log(`res3.status: ${res3.status}`);
				//
				// NOTE: Due to docker being docker, the above request doesn't work correctly and would only download the manifest anyway.
				//       A pipeline or runner should be established somewhere else (e.g. github actions or jenkins) and the download into
				//       the secondary repository should happen there where a full docker client can be run.
            }
        }

    } catch(error) {
        // The platformHttp client throws PlatformHttpClientError if the HTTP request status is 400 or higher
        status = ActionStatus.STOP;
        console.error(`Request failed with status code ${error.status || '<none>'} caused by : ${error.message}`)
    }

    return {
        status,
        message
    }
}