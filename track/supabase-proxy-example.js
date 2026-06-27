/**
 * Optional Express backend adapter for the standalone track widget.
 *
 * Install in your host project (not in this static folder):
 *   npm install express cors @supabase/supabase-js
 *
 * Environment variables:
 *   SUPABASE_URL=https://xxxx.supabase.co
 *   SUPABASE_SERVICE_ROLE_KEY=server-side-key-only
 *   TRACK_ALLOWED_ORIGIN=https://your-production-site.com
 */
const express = require('express');
const cors = require('cors');
const { createClient } = require('@supabase/supabase-js');

const app = express();
const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY);
const allowedOrigin = process.env.TRACK_ALLOWED_ORIGIN;
const numberPattern = /^[A-Za-z0-9]{1,16}$/;

app.use(cors({
  origin: allowedOrigin ? [allowedOrigin] : false,
  methods: ['GET'],
  exposedHeaders: ['Content-Disposition']
}));

app.get('/api/track/:number', async (req, res) => {
  const number = String(req.params.number || '').trim().toUpperCase();
  if (!numberPattern.test(number)) return res.status(400).json({ success: false, message: 'Invalid consignment number format.' });

  const { data, error } = await supabase
    .from('consignments')
    .select('consignment_number,status,pickup_pincode,pickup_address,pickup_tag,pickup_date,drop_pincode,drop_address,drop_tag,drop_date,eta,pod_image')
    .eq('consignment_number', number)
    .single();

  if (error || !data) return res.status(404).json({ success: false, message: 'Consignment not found. Please check the number and try again.' });
  res.json({ success: true, data });
});

app.get('/api/track/:number/pod', async (req, res) => {
  const number = String(req.params.number || '').trim().toUpperCase();
  if (!numberPattern.test(number)) return res.status(400).json({ success: false, message: 'Invalid consignment number format.' });

  const { data, error } = await supabase
    .from('consignments')
    .select('pod_image')
    .eq('consignment_number', number)
    .single();

  if (error || !data || !data.pod_image) return res.status(404).json({ success: false, message: 'No POD found.' });

  // If pod_image is a Supabase Storage path, download it server-side.
  const { data: file, error: fileError } = await supabase.storage.from('pods').download(data.pod_image);
  if (fileError || !file) return res.status(404).json({ success: false, message: 'No POD found.' });

  const arrayBuffer = await file.arrayBuffer();
  res.setHeader('Content-Type', file.type || 'application/octet-stream');
  res.setHeader('Content-Disposition', `attachment; filename="${number}_pod"`);
  res.send(Buffer.from(arrayBuffer));
});

module.exports = app;
