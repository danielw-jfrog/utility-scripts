export default async (context: PlatformContext, data: BeforeDownloadRequestRequest): Promise<BeforeDownloadRequestResponse> => {

    let status: ActionStatus = ActionStatus.PROCEED;
    let message: string = "Proceed";
    try {

        if(data.metadata.name == "manifest.json" || data.metadata.name == "list.manifest.json") {
            console.log("Found a docker manifest or list manifest");

            // Get the labels from the graphql
            let dpackage: string = data.metadata.repoPath.path.split("/", 2).join("/");
            console.log(`Found Package: ${dpackage}`);
            let dtag: string = data.metadata.repoPath.path.split("/", 3).join("/");
            dtag = dtag.substring(dpackage.length + 1);
            console.log(`Found Tag: ${dtag}`);
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

                // Trigger an action to pull the image
                let GH_ORG: string = "danielw-jfrog";
                let GH_REPO: string = "actions-examples";
                let GH_WORKFLOW: string = "pull_docker_image.yml";
                let action_path: string = `https://api.github.com/repos/${GH_ORG}/${GH_REPO}/actions/workflows/${GH_WORKFLOW}/dispatches`;
                let action_inputs: string = `{ "ref": "main", "inputs": { "docker_image": "${dpackage}", "docker_tag": "${dtag}" } }`;

                const res3 = await context.clients.axios.post(action_path, action_inputs, {
                             headers: {
                                 'Accept': 'application/vnd.github+json',
                                 'Authorization': `Bearer ${context.secrets.get('gh_token')}`,
                                 'X-GitHub-Api-Version': '2026-03-10'
                             }
                });
                console.log(`res3.status: ${res3.status}`);
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