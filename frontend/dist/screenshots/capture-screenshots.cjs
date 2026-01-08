const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

async function captureScreenshots() {
    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--window-size=1600,900']
    });

    const pages = [
        { file: 'screenshot-dashboard.html', output: 'screenshot-dashboard.png' },
        { file: 'screenshot-members.html', output: 'screenshot-members.png' },
        { file: 'screenshot-trade-ins.html', output: 'screenshot-trade-ins.png' }
    ];

    const dir = __dirname;

    for (const { file, output } of pages) {
        const page = await browser.newPage();
        await page.setViewport({ width: 1600, height: 900 });

        const filePath = path.join(dir, file);
        console.log(`Capturing ${file}...`);

        await page.goto(`file://${filePath}`, { waitUntil: 'networkidle0' });
        await page.screenshot({
            path: path.join(dir, output),
            fullPage: false
        });

        console.log(`  Saved ${output}`);
        await page.close();
    }

    await browser.close();
    console.log('Done! All screenshots captured.');
}

captureScreenshots().catch(console.error);
