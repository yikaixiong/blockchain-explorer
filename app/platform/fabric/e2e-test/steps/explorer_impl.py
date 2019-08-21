# SPDX-License-Identifier: Apache-2.0

from behave_rest.steps import *
from behave import *
import time
import os
import sys
import uuid
import compose_util
import common_util
import config_util
import shutil
import subprocess
import requests

FNULL = open(os.devnull, 'w')

@when(u'I start explorer')
def start_explorer_impl(context):
    curpath = os.path.realpath('.')
    composeFiles = ["%s/docker-compose/docker-compose-explorer.yaml" % (curpath)]
    if not hasattr(context, "composition_explorer"):
        context.composition_explorer = compose_util.Composition(context, composeFiles,
                                                                projectName=context.projectName,
                                                                startContainers=False)
    else:
        context.composition_explorer.composeFilesYaml = composeFiles

    if hasattr(context, "composition"):
        env = context.composition.getEnv()
        for key,value in env.items():
            context.composition_explorer.environ[key] = value

    context.composition_explorer.up()

    # context.compose_containers = context.composition.collectServiceNames()

@given(u'I start first-network')
@given(u'I start first-network orderer network of type {consensus_type}')
def start_firstnetwork_impl(context, consensus_type="solo"):
    curpath = os.path.realpath('.')
    composeFiles = ["%s/fabric-samples/first-network/docker-compose-explorer.yaml" % (curpath)]
    config_util.makeProjectConfigDir(context)

    shutil.copyfile("{0}/fabric-samples/first-network/crypto-config.yaml".format(curpath), "{0}/configs/{1}/crypto-config.yaml".format(curpath, context.projectName))
    shutil.copyfile("{0}/fabric-samples/first-network/configtx.yaml".format(curpath), "{0}/configs/{1}/configtx.yaml".format(curpath, context.projectName))
    os.mkdir("{0}/configs/{1}/channel-artifacts".format(curpath, context.projectName))
    generateCryptoArtifacts(context, "mychannel", consensus_type)

    # In this step, composition will not be used, clear it once
    if hasattr(context, "composition"):
        del context.composition

    updated_env = config_util.updateEnviron(context)
    updated_env["COMPOSE_PROJECT_NAME"] = context.projectName
    updated_env["CORE_PEER_NETWORKID"] = context.projectName

    os.chdir("{0}/fabric-samples/first-network".format(curpath))

    try:
        command = ["./byfn.sh up -f docker-compose-explorer.yaml -c {0} -o {1}".format("mychannel", consensus_type)]
        subprocess.call(command, shell=True, env=updated_env, stdout=FNULL)
    except:
        print("Failed npm install: {0}".format(sys.exc_info()[1]))

    os.chdir(curpath)

def generateCryptoArtifacts(context, channelID, consensus_type):
    curpath = os.path.realpath('.')
    testConfigs = config_util.makeProjectConfigDir(context)
    updated_env = config_util.updateEnviron(context)
    try:
        command = ["../../fabric-samples/first-network/byfn.sh", "generate", "-f", "docker-compose-explorer.yaml", "-c", channelID, "-o", consensus_type]
        subprocess.call(command, cwd=testConfigs, env=updated_env, stderr=subprocess.STDOUT)
    except:
        print("Unable to generate crypto artifacts: {0}".format(sys.exc_info()[1]))

    try:
        shutil.rmtree("{0}/fabric-samples/first-network/crypto-config".format(curpath), ignore_errors=True)
        shutil.copytree("{0}/crypto-config".format(testConfigs), "{0}/fabric-samples/first-network/crypto-config".format(curpath))
        shutil.copytree("{0}/crypto-config/peerOrganizations".format(testConfigs), "{0}/peerOrganizations".format(testConfigs))
        shutil.copytree("{0}/crypto-config/ordererOrganizations".format(testConfigs), "{0}/ordererOrganizations".format(testConfigs))
    except:
        print("Unable to copy crypto artifacts: {0}".format(sys.exc_info()[1]))

    try:
        shutil.rmtree("{0}/fabric-samples/first-network/channel-artifacts".format(curpath), ignore_errors=True)
        shutil.copytree("{0}/channel-artifacts".format(testConfigs), "{0}/fabric-samples/first-network/channel-artifacts".format(curpath))
    except:
        print("Unable to copy channel artifacts: {0}".format(sys.exc_info()[1]))


@given(u'I start balance-transfer')
@given(u'I start balance-transfer orderer network of type {consensus_type}')
def start_balancetransfer_impl(context, consensus_type="solo"):
    testConfigs = config_util.makeProjectConfigDir(context)
    curpath = os.path.realpath('.')
    shutil.copytree(
        "%s/fabric-samples/balance-transfer/artifacts/channel/crypto-config/ordererOrganizations" % (curpath),
        "%s/%s/ordererOrganizations" % (curpath, testConfigs)
    )
    shutil.copytree(
        "%s/fabric-samples/balance-transfer/artifacts/channel/crypto-config/peerOrganizations" % (curpath),
        "%s/%s/peerOrganizations" % (curpath, testConfigs)
    )

    os.chdir("{0}/fabric-samples/balance-transfer".format(curpath))

    # In this step, composition will not be used, clear it once
    if hasattr(context, "composition"):
        del context.composition

    updated_env = config_util.updateEnviron(context)
    updated_env["COMPOSE_PROJECT_NAME"] = context.projectName
    updated_env["CORE_PEER_NETWORKID"] = context.projectName

    try:
        command = ["npm install --silent"]
        subprocess.call(command, shell=True, env=updated_env, stdout=FNULL)
    except:
        print("Failed npm install: {0}".format(sys.exc_info()[1]))

    try:
        command = ["./runApp.sh"]
        p = subprocess.Popen(command, shell=True, env=updated_env, stdout=subprocess.PIPE)
    except:
        print("Failed to start application: {0}".format(sys.exc_info()[1]))

    while True:
        line = p.stdout.readline()
        if "SERVER STARTED" in line:
            print(line)
            break
        else:
            time.sleep(1)

    try:
        command = ["./testAPIs.sh"]
        subprocess.call(command, shell=True, env=updated_env, stdout=FNULL)
    except:
        print("Failed to exectute REST API: {0}".format(sys.exc_info()[1]))

    os.chdir(curpath)

@step('I make a {request_verb} request to the following path segment')
def request_to_the_path_described_on_table(context, request_verb):
    if not hasattr(context, 'verify_ssl'):
        context.verify_ssl = True

    url = context.base_url

    for row in context.table:
        for x in context.table.headings:
            path = row[x]
            print(path)
            if path.startswith("context") and path[8:] == "block_height":
                # TODO messy code
                # This attribute should be integer
                url = url + '/' + str(getattr(context, path[8:]) - 1).encode('ascii')
            elif path.startswith("context"):
                url = url + '/' + str(getattr(context, path[8:])).encode('ascii')
            else:
                url = url + '/' + path

    print(url)
    context.r = getattr(requests, request_verb.lower())(url, headers=context.headers, verify=context.verify_ssl)

    log_full(context.r)

    return context.r

@then(u'the explorer app logs contains "{data}" {count:d} time(s) within {timeout:d} seconds')
def step_impl(context, data, count, timeout):
    time.sleep(float(timeout))
    data_count = is_in_log("explorer.mynetwork.com", data)
    assert data_count == count, "The log didn't appear the expected number of times({0}).".format(data_count)

@then(u'the explorer app logs contains "{data}" within {timeout:d} seconds')
def step_impl(context, data, timeout):
    time.sleep(float(timeout))
    data_count = is_in_log("explorer.mynetwork.com", data)
    assert data_count > 0, "The log didn't appear at all."

@when(u'"{container}" is stopped')
def step_impl(context, container):
    if hasattr(context, "composition") and hasattr(context, "composeFilesYaml"):
        print('composition')
        context.composition.stop([container])
    elif hasattr(context, "composition_explorer"):
        print('composition_explorer')
        context.composition_explorer.stop([container])
    else:
        assert False, "Failed to stop container {0}".format(container)

def is_in_log(container, keyText):
    output = subprocess.check_output(
        "docker exec  " + container + " cat logs/app/app.log | grep " + "\"" + keyText + "\"" + " | wc -l",
        shell=True)
    return int(output)
