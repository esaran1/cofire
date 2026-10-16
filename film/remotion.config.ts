/**
 * Render settings for the Remotion CLI (studio, still). Everything runs
 * locally: no Lambda, no cloud, no browser download. The browser and the
 * webpack override are shared with the Node scripts (scripts/browser.mjs,
 * scripts/webpack.mjs).
 */
import { Config } from "@remotion/cli/config";
import { headlessShell } from "./scripts/browser.mjs";
import { webpackOverride } from "./scripts/webpack.mjs";

Config.setBrowserExecutable(headlessShell());
Config.setChromiumOpenGlRenderer("swangle");
Config.setVideoImageFormat("jpeg");
Config.setJpegQuality(94);
Config.setOverwriteOutput(true);
Config.setConcurrency(4);
Config.overrideWebpackConfig(webpackOverride);
